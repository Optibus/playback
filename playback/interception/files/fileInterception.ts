import * as base64 from 'base64-js';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { Timed } from '../../utils/timingUtils';

class FileInterception {
    private file_path_arg_index: number;
    private file_path_arg_name: string;
    private intercepted_size_limit: number | null;
    private static ABOVE_LIMIT_CONTENT: string = 'above interception limit';

    constructor(file_path_arg_index: number, file_path_arg_name: string, intercepted_size_limit: number | null = null) {
        this.file_path_arg_index = file_path_arg_index;
        this.file_path_arg_name = file_path_arg_name;
        this.intercepted_size_limit = this.calculateMaxInterceptedSizeLimit(intercepted_size_limit);
    }

    private calculateMaxInterceptedSizeLimit(intercepted_size_limit: number | null): number {
        if (intercepted_size_limit !== null) {
            return intercepted_size_limit;
        }
        return parseInt(process.env.PLAYBACK_INTERCEPTED_FILE_SIZE_LIMIT || "500", 10);
    }

    private getFilePath(args: any[], kwargs: Record<string, any>): string {
        let file_path: string = kwargs[this.file_path_arg_name];
        if (!file_path) {
            file_path = args[this.file_path_arg_index];
        }
        return file_path;
    }

    private interceptFile(args: any[], kwargs: Record<string, any>): Record<string, string> {
        const file_path: string = this.getFilePath(args, kwargs);

        if (this.isFileAboveSizeLimit(file_path)) {
            return this.aboveLimitResult(file_path);
        }

        console.info(`Reading intercepted file (${file_path})`);

        const timed = new Timed();
        timed.start();
        const content: Buffer = fs.readFileSync(file_path);
        console.info(`Done reading content size is ${this.mbSize(content.length)}MB (${file_path})`);
        const result = this.serializeFile(content, file_path);

        console.info(`Done preparing file for recording within ${timed.duration()}s (${file_path})`);
        return result;
    }

    private isFileAboveSizeLimit(file_path: string): boolean {
        if (this.intercepted_size_limit !== null) {
            const file_size_in_mb: number = this.mbSize(fs.statSync(file_path).size);
            if (file_size_in_mb > this.intercepted_size_limit) {
                console.info(`Intercepted file is ${file_size_in_mb}MB which is above interception limit of ${this.intercepted_size_limit}MB, ignoring content in file ${file_path}`);
                return true;
            }
        }
        return false;
    }

    private aboveLimitResult(file_path: string): Record<string, string> {
        return {
            file_path: file_path,
            file_content: FileInterception.ABOVE_LIMIT_CONTENT
        };
    }

    private serializeFile(content: Buffer, file_path: string): Record<string, string> {
        const encoded_content: string = base64.fromByteArray(content);
        return {
            file_path: file_path,
            file_content: encoded_content
        };
    }

    private static deserializeFile(serialized_file: Record<string, string>): [string, Buffer] {
        let file_content: string | Buffer = serialized_file['file_content'];

        if (file_content !== FileInterception.ABOVE_LIMIT_CONTENT) {
            file_content = base64.toByteArray(file_content);
        }

        return [serialized_file['file_path'], file_content];
    }

    private mbSize(size: number): number {
        return size / (1024.0 * 1024.0);
    }
}

export { FileInterception };
