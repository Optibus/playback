import { EqualityStatus, ComparatorResult, Comparison, CompareExecutionConfig, PlayAndCompareResult } from "./types";
import { Playback } from "../tapeRecorder"; // Assuming tapeRecorder.ts exports Playback
import { Exception } from "../exceptions"; // Assuming exceptions.ts exports Exception
import * as logging from "logging"; // Placeholder for actual logging module

const _logger = logging.getLogger(__name__);

class Equalizer {
    private recordingIds: IterableIterator<string>;
    private player: (recordingId: string) => Playback;
    private resultExtractor: (output: any) => any;
    private comparisonDataExtractor: (recording: any) => any | null;
    private comparator: (expected: any, actual: any, ...args: any[]) => ComparatorResult;
    private compareExecutionConfig: CompareExecutionConfig;
    private _compareTasks: Queue<string>;
    private _compareResults: Queue<PlayAndCompareResult>;
    private _terminateProcess: boolean;
    private _compareProcess: Process | null;
    private _compareProcessAge: number;

    constructor(recordingIds: IterableIterator<string>, player: (recordingId: string) => Playback, resultExtractor: (output: any) => any, comparator: (expected: any, actual: any, ...args: any[]) => ComparatorResult, comparisonDataExtractor: (recording: any) => any | null = null, compareExecutionConfig: CompareExecutionConfig = new CompareExecutionConfig()) {
        this.recordingIds = recordingIds;
        this.player = player;
        this.resultExtractor = resultExtractor;
        this.comparisonDataExtractor = comparisonDataExtractor;
        this.comparator = comparator;
        this.compareExecutionConfig = compareExecutionConfig;
        // Init multiprocess related properties
        this._compareTasks = new Queue<string>();
        this._compareResults = new Queue<PlayAndCompareResult>();
        this._terminateProcess = false;
        this._compareProcess = null;
        this._compareProcessAge = 0;
    }

    public runComparison(): IterableIterator<Comparison> {
        const counter = new Counter<EqualityStatus>();
        let iteration = 0;
        let completed = false;
        try {
            for (const recordingId of this.recordingIds) {
                try {
                    const playAndCompareResult = this._playAndCompareRecordingWithinWorker(recordingId);
                    const playback = playAndCompareResult.playback;

                    let recordedResult: any = null;
                    let playbackResult: any = null;
                    if (playback !== null && this.compareExecutionConfig.keepResultsInComparison) {
                        recordedResult = this.resultExtractor(playback.recordedOutputs);
                        playbackResult = this.resultExtractor(playback.playbackOutputs);
                    }

                    const comparison = new Comparison(
                        playAndCompareResult.comparatorResult,
                        recordedResult,
                        playbackResult,
                        playAndCompareResult.recordedResultIsException,
                        playAndCompareResult.playbackResultIsException,
                        playback,
                        recordingId
                    );

                    _logger.info(`Recording ${recordingId} Comparison result: ${comparison}`);

                    counter.increment(comparison.comparatorStatus.equalityStatus);

                    if (iteration % 10 === 0) {
                        _logger.info(`Iteration ${iteration} ${Equalizer._comparisonStatsRepr(counter)}`);
                    }

                    yield comparison;
                } catch (ex) {
                    counter.increment(EqualityStatus.EqualizerFailure);
                    yield new Comparison(
                        ComparatorResult.failureResult(recordingId, ex),
                        null,
                        null,
                        false,
                        false,
                        null,
                        recordingId);
                }
            }

            completed = true;

        } finally {
            this._terminateProcess = true;
            this._compareTasks.close();
            this._compareResults.close();
            const logPrefix = completed ? "Completed all" : "Error during playback, executed";
            _logger.info(`${logPrefix} ${iteration} iterations, ${Equalizer._comparisonStatsRepr(counter)}`);
        }
    }

    private _playAndCompareRecordingWithinWorker(recordingId: string): PlayAndCompareResult {
        if (!this.compareExecutionConfig.compareInDedicatedProcess) {
            return this._playAndCompareRecording(recordingId);
        }

        this._createOrRecyclePlayerProcessIfNeeded();

        // Queue the task for the playback process and wait for its result
        this._compareTasks.put(recordingId);
        const start_time = Date.now();
        let timedOut = true;
        while (Date.now() - start_time <= this.compareExecutionConfig.compareProcessTimeout) {
            try {
                const [succeeded, result] = this._compareResults.get(true, 1);
                timedOut = false;

                if (!succeeded) {
                    throw new Error(result);
                }

                break;
            } catch (error) {
                if (error instanceof QueueEmptyError) {
                    if (!this._compareProcess.isAlive()) {
                        this._compareProcess = null;
                        throw new Error("playback process have died");
                    }
                }
            }
        }

        if (timedOut) {
            this._handleCompareExecutionTimeout();
        }

        return result;
    }

    private _handleCompareExecutionTimeout(): void {
        _logger.warning('Waiting for comparison result timed out');
        if (this._compareProcess.isAlive()) {
            try {
                this._killCompareProcess();
            } catch (ex) {
                _logger.warning(`Error while killing worker, ${ex}`);
            }
        }
        this._compareProcess = null;
        throw new Error("timeout while running recording playback and comparison");
    }

    private _killCompareProcess(): void {
        process.kill(this._compareProcess.pid, 'SIGKILL');
    }

    private _createOrRecyclePlayerProcessIfNeeded(): void {
        if (this._compareProcess !== null && this._compareProcessAge >= this.compareExecutionConfig.compareProcessRecycleRate) {
            this._terminateProcess = true;
            this._compareProcess.join();
            this._compareProcess = null;
            this._terminateProcess = false;
        }

        if (this._compareProcess === null) {
            this._createNewPlayerProcess();
        }

        this._compareProcessAge += 1;
    }

    private _createNewPlayerProcess(): void {
        this._compareProcess = new Process(() => this._playbackProcessTarget(), "Playback runner");
        this._compareProcess.start();
        this._compareProcessAge = 0;
    }

    private _playbackProcessTarget(): void {
        while (!this._terminateProcess) {
            try {
                const recordingId = this._compareTasks.get(true, 0.05);
                try {
                    const executionResult = this._playAndCompareRecording(recordingId);
                    this._compareResults.put([true, executionResult]);
                } catch (ex) {
                    _logger.info(`Failure during play and compare in playback process of id ${recordingId} - ${ex}`);
                    this._compareResults.put([false, ex.toString()]);
                }
            } catch (error) {
                if (error instanceof QueueEmptyError) {
                    // Expected to happen regularly
                }
            }
        }
    }

    private _playAndCompareRecording(recordingId: string): PlayAndCompareResult {
        let playback: Playback | null = null;
        let recordedResultIsException: boolean | null = null;
        let playbackResultIsException: boolean | null = null;

        try {
            playback = this.player(recordingId);

            const recordedResult = this.resultExtractor(playback.recordedOutputs);
            const playbackResult = this.resultExtractor(playback.playbackOutputs);

            recordedResultIsException = recordedResult instanceof Exception;
            playbackResultIsException = playbackResult instanceof Exception;

            const comparisonData = this.comparisonDataExtractor ? this.comparisonDataExtractor(playback.originalRecording) : {};

            const comparatorResult = this.comparator(recordedResult, playbackResult, comparisonData);
            if (!(comparatorResult instanceof ComparatorResult)) {
                comparatorResult = new ComparatorResult(comparatorResult);
            }

            return new PlayAndCompareResult(comparatorResult, playback, recordedResultIsException, playbackResultIsException);

        } catch (ex) {
            return new PlayAndCompareResult(ComparatorResult.failureResult(recordingId, ex), playback, recordedResultIsException, playbackResultIsException);
        }
    }

    private static _comparisonStatsRepr(counter: Counter<EqualityStatus>): string {
        return `comparison stats: (equal - ${counter.get(EqualityStatus.Equal)}, fixed - ${counter.get(EqualityStatus.Fixed)}, diff - ${counter.get(EqualityStatus.Different)}, failed - ${counter.get(EqualityStatus.Failed)}, equalizer failures - ${counter.get(EqualityStatus.EqualizerFailure)})`;
    }

    public static getExceptionStackTrace(): string {
        const traceBack = new Error().stack;
        return traceBack ? traceBack : "";
    }
}
