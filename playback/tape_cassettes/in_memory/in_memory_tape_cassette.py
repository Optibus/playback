import { TapeCassette } from "../../tapeCassette";
import { MemoryRecording } from "../../recordings/memory/memoryRecording";
import { encode, decode } from "jsonpickle";
import { v1 as uuid } from "uuid";
import { shuffle } from "lodash";

export class InMemoryTapeCassette implements TapeCassette {
    private _recordings: Map<string, string>;
    private _lastId: string | null;

    constructor() {
        this._recordings = new Map<string, string>();
        this._lastId = null;
    }

    createNewRecording(category: string): MemoryRecording {
        return new MemoryRecording(`${category}/${uuid()}`);
    }

    saveRecording(recording: MemoryRecording): void {
        this._recordings.set(recording.id, encode(recording, {unpicklable: true}));
        this._lastId = recording.id;
    }

    getRecording(recordingId: string): MemoryRecording | null {
        const serializedRecording = this._recordings.get(recordingId);
        if (!serializedRecording) {
            return null;
        }
        const deserializedForm = decode(serializedRecording) as MemoryRecording;
        return new MemoryRecording(deserializedForm.id, deserializedForm.recordingData, deserializedForm.recordingMetadata);
    }

    iterRecordingIds(category: string, start_date?: Date, end_date?: Date, metadata?: any, limit?: number, randomResults: boolean = false): IterableIterator<string> {
        let result: string[] = [];
        for (const [recordingId, serializedRecording] of this._recordings) {
            const recording = decode(serializedRecording) as MemoryRecording;
            if (this.extractRecordingCategory(recordingId) !== category) {
                continue;
            }

            if (metadata && !TapeCassette.matchAgainstRecordedMetadata(metadata, recording.getMetadata())) {
                continue;
            }

            result.push(recordingId);
        }

        if (limit) {
            result = result.slice(0, limit);
        }

        if (randomResults) {
            shuffle(result);
        }

        return result[Symbol.iterator]();
    }

    extractRecordingCategory(recordingId: string): string {
        return recordingId.split('/')[0];
    }

    getLastRecordingId(): string | null {
        return this._lastId;
    }

    getAllRecordingIds(): string[] {
        return Array.from(this._recordings.keys()).sort();
    }
}
