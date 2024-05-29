import { FileInterception } from "./fileInterception";
import { OutputInterceptionDataHandler } from "../outputInterception";

class OutputInterceptionFileDataHandler implements OutputInterceptionDataHandler, FileInterception {
    /**
    * Intercept file arguments for playback
    */
    prepareOutputForRecording(interceptionKey: string, args: any[], kwargs: object): object {
        return this.interceptFile(args, kwargs);
    }

    restoreOutputFromRecording(recordedData: any): InterceptedOutputFileHolder {
        const [filePath, fileContent] = this.deserializeFile(recordedData);
        return new InterceptedOutputFileHolder(fileContent, filePath);
    }
}

class InterceptedOutputFileHolder {
    fileContent: string;
    outputFilePath: string;

    constructor(fileContent: string, outputFilePath: string) {
        this.fileContent = fileContent;
        this.outputFilePath = outputFilePath;
    }

    toFile(filePath: string): void {
        const fs = require("fs");
        fs.writeFileSync(filePath, this.fileContent);
    }
}
