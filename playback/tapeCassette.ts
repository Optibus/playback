interface TapeCassette {
    getRecording(recordingId: string): any; // Adjusted to TypeScript syntax
    getRecordingMetadata(recordingId: string): object; // Adjusted to TypeScript syntax
    createNewRecording(category: any): any; // Adjusted to TypeScript syntax
    abortRecording(recording?: any): void; // Adjusted to TypeScript syntax
    saveRecording(recording: any): void; // Adjusted to TypeScript syntax
    _saveRecording(recording: any): void; // Adjusted to TypeScript syntax
    iterRecordingIds(category: string, startDate?: Date, endDate?: Date, metadata?: object, limit?: number, randomResults?: boolean): IterableIterator<string>; // Adjusted to TypeScript syntax
    iterRecordingsMetadata(category: string, startDate?: Date, endDate?: Date, metadata?: object, limit?: number): IterableIterator<object>; // Adjusted to TypeScript syntax
    static matchAgainstRecordedMetadata(filterByMetadata: object, recordingMetadata: object): boolean; // Adjusted to TypeScript syntax
    static _matchMetadataValue(matchValue: any, recordedValue: any): boolean; // Adjusted to TypeScript syntax
    static _operatorFilter(recordedValue: any, metadataValue: object): boolean; // Adjusted to TypeScript syntax
    extractRecordingCategory(recordingId: string): string; // Adjusted to TypeScript syntax
    close(): void; // Adjusted to TypeScript syntax
}
