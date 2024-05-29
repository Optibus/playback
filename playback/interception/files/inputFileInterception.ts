import { FileInterception } from "./fileInterception";
import { InputInterceptionDataHandler } from "../inputInterception";

class InputInterceptionFileDataHandler implements InputInterceptionDataHandler, FileInterception {
    /**
    * Intercept file arguments for playback
    */
    prepareInputForRecording(interceptionKey: string, result: any, args: any[], kwargs: { [key: string]: any }): { [key: string]: string } {
        /**
        * Reads the intercepted file, encode its content as string and return it ready for recording
        * @param interceptionKey: Input interception key
        * @param result: Input function invocation result (the input)
        * @param args: Input invocation args
        * @param kwargs: Input invocation kwargs
        * @return: Input result in a form that should be saved in the recording
        */
        return this._interceptFile(args, kwargs);
    }

    restoreInputFromRecording(recordedData: any, args: any[], kwargs: { [key: string]: any }): string {
        /**
        * Create a file from the recorded content and place it in the given file path
        * @param recordedData: Recorded data provided by the prepare method
        * @param args: Input invocation args
        * @param kwargs: Input invocation kwargs
        * @return: Path of restored file
        */
        const filePath = this._getFilePath(args, kwargs);
        const fs = require("fs");
        fs.writeFileSync(filePath, this._deserializeFile(recordedData)[1], { encoding: "binary" });

        return filePath;
    }
}
