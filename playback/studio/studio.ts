import { Equalizer, CompareExecutionConfig, Comparison } from "../equalizer";
import { RecordingLookupProperties, findMatchingRecordingIds } from "../recordingsLookup";
import { TapeRecorder } from "../../tapeRecorder";
import { EqualizerTuner } from "../equalizerTuning";
import { Logger } from "tslog";
import { DateTime } from "luxon";

const logger: Logger = new Logger({ name: "PlaybackStudio" });

class PlaybackStudio {
    private static DEFAULT_LOOKUP_PROPERTIES: RecordingLookupProperties = new RecordingLookupProperties(
        DateTime.utc().minus({ days: 7 }), undefined, undefined, 20
    );

    constructor(
        private categories: string[],
        private equalizerTuner: EqualizerTuner,
        private tapeRecorder: TapeRecorder,
        private lookupProperties: RecordingLookupProperties = PlaybackStudio.DEFAULT_LOOKUP_PROPERTIES,
        private recordingIds?: string[],
        private compareExecutionConfig?: CompareExecutionConfig
    ) {}

    public play(): Map<string, IterableIterator<Comparison | Error>> {
        const categoriesRecordings: Map<string, string[]> = this.recordingIds
            ? this.groupRecordingIdsByCategories()
            : new Map(this.categories.map(category => [category, undefined]));

        const result: Map<string, IterableIterator<Comparison | Error>> = new Map();
        categoriesRecordings.forEach((recordingIds, category) => {
            result.set(category, this.playCategory(category, recordingIds));
        });
        return result;
    }

    private groupRecordingIdsByCategories(): Map<string, string[]> {
        const grouping: Map<string, string[]> = new Map();
        this.recordingIds.forEach(recordingId => {
            const category: string = this.tapeRecorder.tapeCassette.extractRecordingCategory(recordingId);
            const recordings: string[] = grouping.get(category) || [];
            recordings.push(recordingId);
            grouping.set(category, recordings);
        });
        return new Map([...grouping.entries()].sort());
    }

    private playCategory(category: string, recordingIds?: string[]): IterableIterator<Comparison | Error> {
        logger.info(`Playing Category ${category}`);
        let tuning;
        try {
            tuning = this.equalizerTuner.createCategoryTuning(category);
        } catch (ex) {
            logger.info(`Cannot tune equalizer for category ${category} - ${ex}`);
            return [ex][Symbol.iterator]();
        }

        const recordingIdIterator: IterableIterator<string> = recordingIds
            ? recordingIds[Symbol.iterator]()
            : findMatchingRecordingIds(this.tapeRecorder, category, this.lookupProperties);

        const player = (recordingId: string) => this.tapeRecorder.play(recordingId, tuning.playbackFunction);

        const equalizer: Equalizer = new Equalizer(
            recordingIdIterator,
            player,
            tuning.resultExtractor,
            tuning.comparator,
            tuning.comparisonDataExtractor,
            this.compareExecutionConfig
        );
        return equalizer.runComparison();
    }
}

export { PlaybackStudio };
