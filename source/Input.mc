import Toybox.WatchUi;

class Input extends WatchUi.BehaviorDelegate {
    private var _parentView as View;

    public function initialize(view as View) {
        BehaviorDelegate.initialize();
        _parentView = view;
    }

    public function onSelect() as Boolean {
        return true;
    }
}
