import Toybox.Application;

import BumpTools;

class App extends Application.AppBase {
    public function initialize() {
        AppBase.initialize();
    }

    public function getInitialView() as Array<Views or InputDelegates>? {
        var history = new BumpTools.AccelerationHistory(200);
        var recorder = new BumpTools.Recorder(history);
        var mainView = new View(history);
        var input = new Input(mainView, recorder);
        return [mainView, input] as Array<Views or InputDelegates>;
    }
}
