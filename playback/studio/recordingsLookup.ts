import { TapeRecorder } from "../tapeRecorder";

interface RecordingLookupProperties {
    start_date: Date;
    end_date?: Date;
    metadata?: any;
    limit?: number;
    random_sample?: boolean;
    skip_incomplete?: boolean;

    constructor(start_date: Date, end_date?: Date, metadata?: any, limit?: number, random_sample?: boolean, skip_incomplete?: boolean) {
        this.start_date = start_date;
        this.end_date = end_date;
        this.metadata = metadata;
        this.limit = limit;
        this.random_sample = random_sample;
        this.skip_incomplete = skip_incomplete;
    }
}

function findMatchingRecordingIds(tapeRecorder: TapeRecorder, category: string, lookupProperties: RecordingLookupProperties): IterableIterator<string> {
    let metadata = lookupProperties.metadata;
    if (lookupProperties.skip_incomplete) {
        metadata = metadata || {};
        // We also add null to support recordings that were created before adding the INCOMPLETE_RECORDING metadata
        metadata[TapeRecorder.INCOMPLETE_RECORDING] = [false, null];
    }
    const recordingIds = tapeRecorder.tapeCassette.iterRecordingIds(
        category, lookupProperties.start_date, lookupProperties.end_date,
        metadata,
        lookupProperties.limit,
        lookupProperties.random_sample);

    return recordingIds;
}
