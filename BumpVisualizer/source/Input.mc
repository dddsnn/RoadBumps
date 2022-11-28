import Toybox.WatchUi;
import Toybox.System;

class Input extends WatchUi.InputDelegate {
    private var _view as View;

    public function initialize(view as View) {
        InputDelegate.initialize();
        _view = view;
    }

    public function onKey(keyEvent as WatchUi.KeyEvent) as Boolean {
        switch (keyEvent.getKey()) {
        case WatchUi.KEY_ESC:
            System.exit();
            break;
        }
        return true;
    }
}
