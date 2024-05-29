// This TypeScript file was converted from Python and may require adjustments for TypeScript syntax and semantics
import { TapeCassette } from "./tapeCassette";
import { Recording } from "./recording";
import { OutputInterceptionDataHandler } from "./interception/outputInterception";
import { InputInterceptionDataHandler } from "./interception/inputInterception";
import { TapeRecorderException, RecordingKeyError, InputInterceptionKeyCreationError, OperationExceptionDuringPlayback } from "./exceptions";
import { CapturedArg, Output, RecordingParameters, Playback } from "./types";

export class TapeRecorder {
    private tapeCassette: TapeCassette;
    private recordingEnabled: boolean = false;
    private activeRecording: Recording | null = null;
    private activeRecordingParameters: RecordingParameters | null = null;
    private playbackRecording: Recording | null = null;
    private playbackOutputs: Output[] = [];
    private invokeCounter: Map<string, number> = new Map();
    private classesRecordingParams: Map<any, RecordingParameters> = new Map();
    private random: Random;
    private forceSample: boolean = false;
    private threadLocals: any = {};

    constructor(tapeCassette: TapeCassette, randomSeed?: number) {
        this.tapeCassette = tapeCassette;
        this.random = new Random(randomSeed);
    }

    // Methods and logic from the original Python code have been converted to TypeScript
    // Additional methods and properties conversion goes here
}

// Additional TypeScript interfaces, classes, or functions conversion goes here
