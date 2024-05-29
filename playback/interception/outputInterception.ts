interface OutputInterceptionDataHandler {
    prepareOutputForRecording(interceptionKey: string, args: any[], kwargs: object): any;
    restoreOutputFromRecording(recordedData: any): any;
}
