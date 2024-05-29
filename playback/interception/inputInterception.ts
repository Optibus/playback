interface InputInterceptionDataHandler {
    /**
     * Prepare the input result that should be saved in the recording
     * @param interceptionKey: Input interception key
     * @param result: Input function invocation result (the input)
     * @param args: Input invocation args
     * @param kwargs: Input invocation kwargs
     * @return Input result in a form that should be saved in the recording
     */
    prepareInputForRecording(interceptionKey: string, result: any, args: any[], kwargs: object): any;

    /**
     * Restore the actual input from the recording
     * @param recordedData: Recorded data provided by the prepare method
     * @param args: Input invocation args
     * @param kwargs: Input invocation kwargs
     * @return Input saved to the recording
     */
    restoreInputFromRecording(recordedData: any, args: any[], kwargs: object): any;
}
