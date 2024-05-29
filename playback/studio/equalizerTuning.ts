interface EqualizerTuning {
    playbackFunction: Function;
    resultExtractor: Function;
    comparator: Function;
    comparisonDataExtractor?: Function;

    constructor(playbackFunction: Function, resultExtractor: Function, comparator: Function, comparisonDataExtractor?: Function) {
        this.playbackFunction = playbackFunction;
        this.resultExtractor = resultExtractor;
        this.comparator = comparator;
        this.comparisonDataExtractor = comparisonDataExtractor;
    }
}

interface EqualizerTuner {
    createCategoryTuning(category: string): EqualizerTuning;
}
