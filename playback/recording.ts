import { v1 as uuid } from 'uuid';

interface IRecording {
    id: string;
    set_data(key: string, value: any): void;
    get_data(key: string): any;
    get_data_direct(key: string): any;
    get_all_keys(): string[];
    add_metadata(metadata: Record<string, any>): void;
    get_metadata(): Record<string, any>;
}

abstract class Recording implements IRecording {
    id: string;
    private _closed: boolean;

    constructor(_id?: string) {
        this.id = _id || uuid();
        this._closed = false;
    }

    abstract _set_data(key: string, value: any): void;

    set_data(key: string, value: any): void {
        if (!this._closed) {
            this._set_data(key, value);
        }
    }

    abstract get_data(key: string): any;

    abstract get_data_direct(key: string): any;

    abstract get_all_keys(): string[];

    add_metadata(metadata: Record<string, any>): void {
        if (!this._closed) {
            this._add_metadata(metadata);
        }
    }

    abstract _add_metadata(metadata: Record<string, any>): void;

    close(): void {
        this._closed = true;
    }

    abstract get_metadata(): Record<string, any>;
}
