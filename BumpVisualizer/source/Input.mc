import Toybox.WatchUi;
import Toybox.System;

class Input extends WatchUi.InputDelegate {
    private var _view as View;
    private var _recorder as Recorder;

    public function initialize(view as View, recorder as Recorder) {
        InputDelegate.initialize();
        _view = view;
        _recorder = recorder;
    }

    public function onKey(keyEvent as WatchUi.KeyEvent) as Boolean {
        switch (keyEvent.getKey()) {
        case WatchUi.KEY_START:
            var isRecording = _recorder.toggleRecording();
            _view.setRecordingStatus(isRecording);
            break;
        case WatchUi.KEY_ESC:
            System.exit();
            break;
        }
        return true;
    }
}
