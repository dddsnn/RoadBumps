import Toybox.Application;

class App extends Application.AppBase {
    public function initialize() {
        AppBase.initialize();
    }

    public function getInitialView() as Array<Views or InputDelegates>? {
        var history = new AccelerationHistory(200);
        var mainView = new View(history);
        var viewDelegate = new Input(mainView);
        return [mainView, viewDelegate] as Array<Views or InputDelegates>;
    }
}
