import Toybox.Application;

import BumpTools;

class App extends Application.AppBase {
    private var _history as BumpTools.AccelerationHistory? = null;
    private var _recorder as BumpTools.Recorder? = null;
    private var _mainView as View? = null;
    private var _input as Input? = null;
    public function initialize() {
        AppBase.initialize();
    }

    public function getInitialView() as Array<Views or InputDelegates>? {
        _history = new BumpTools.AccelerationHistory(200);
        _recorder = new BumpTools.Recorder(_history);
        _mainView = new View(_history);
        _input = new Input(_mainView, _recorder);
        return [_mainView, _input] as Array<Views or InputDelegates>;
    }

    public function onStop(state as Lang.Dictionary?) as Void {
        AppBase.onStop(state);
        _history.close();
    }
}
