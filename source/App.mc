import Toybox.Application;

class App extends Application.AppBase {
    public function initialize() {
        AppBase.initialize();
    }

    public function getInitialView() as Array<Views or InputDelegates>? {
        var mainView = new View();
        var viewDelegate = new Input(mainView);
        return [mainView, viewDelegate] as Array<Views or InputDelegates>;
    }
}
