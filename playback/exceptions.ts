class TapeRecorderException extends Error {
    constructor(message?: string) {
        super(message);
        this.name = "TapeRecorderException";
    }
}

class InputInterceptionKeyCreationError extends TapeRecorderException {
    constructor(message?: string) {
        super(message);
        this.name = "InputInterceptionKeyCreationError";
    }
}

class RecordingKeyError extends TapeRecorderException {
    constructor(message?: string) {
        super(message);
        this.name = "RecordingKeyError";
    }
}

class OperationExceptionDuringPlayback extends TapeRecorderException {
    constructor(message?: string) {
        super(message);
        this.name = "OperationExceptionDuringPlayback";
    }
}

class NoSuchRecording extends TapeRecorderException {
    recordingId: string;

    constructor(recordingId: string) {
        super(`No such recording: ${recordingId}`);
        this.name = "NoSuchRecording";
        this.recordingId = recordingId;
    }
}
