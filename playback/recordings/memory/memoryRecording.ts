import { Recording } from "../../recording";
import { RecordingKeyError } from "../../exceptions";
import { pickleCopy } from "../../utils/pickleCopy";

export class MemoryRecording extends Recording {
    private recordingData: { [key: string]: any };
    private recordingMetadata: { [key: string]: any };

    constructor(_id?: string, recordingData?: { [key: string]: any }, recordingMetadata?: { [key: string]: any }) {
        super(_id);
        this.recordingData = recordingData || {};
        this.recordingMetadata = recordingMetadata || {};
    }

    protected _setData(key: string, value: any): void {
        this.recordingData[key] = value;
    }

    public getData(key: string): any {
        // The contract of the recording requires the implementation to always return a fresh copy of the data.
        // It prevents in place modifications that may be done by the calling code to influence the outcome
        // of the recording playback. That's why we copy here.
        return pickleCopy(this.getDataDirect(key));
    }

    public getDataDirect(key: string): any {
        if (!(key in this.recordingData)) {
            throw new RecordingKeyError(`Key '${key}' not found in recording`);
        }

        return this.recordingData[key];
    }

    public getAllKeys(): string[] {
        return Object.keys(this.recordingData);
    }

    protected _addMetadata(metadata: { [key: string]: any }): void {
        Object.assign(this.recordingMetadata, metadata);
    }

    public getMetadata(): { [key: string]: any } {
        return this.recordingMetadata;
    }
}
