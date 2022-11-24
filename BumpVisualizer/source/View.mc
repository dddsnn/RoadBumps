import Toybox.Graphics;
import Toybox.Lang;
import Toybox.Timer;
import Toybox.WatchUi;

class View extends WatchUi.View {
    const BAR_WIDTH as Lang.Number = 2;
    const GRAPH_LIMIT_MILLI_G = 4000;

    private var _history as AccelerationHistory;
    private var _isRecording as Boolean = false;
    private var _width as Lang.Number;
    private var _graph as BumpTools.AccelerationGraph?;

    public function initialize(history as AccelerationHistory) {
        View.initialize();
        _history = history;
        _history.subscribe(method(:refresh));
    }

    public function onLayout(dc as Dc) {
        _width = dc.getWidth();
        _graph = new BumpTools.AccelerationGraph(
            _history, 0, 50, _width, dc.getHeight() - 50, BAR_WIDTH,
            GRAPH_LIMIT_MILLI_G);
    }

    public function refresh(numNew as Lang.Number) as Void {
        WatchUi.requestUpdate();
    }

    public function onUpdate(dc as Dc) as Void {
        resetColors(dc);
        dc.clear();
        drawInfo(dc);
        _graph.draw(dc);
    }

    private function resetColors(dc as Dc) as Void {
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_BLACK);
    }

    private function drawInfo(dc as Graphics.Dc) {
        var y = 5;
        var font = Graphics.FONT_XTINY;
        dc.drawText(_width / 2, y, font, Lang.format("sample rate: $1$", [_history.getSampleRate()]), Graphics.TEXT_JUSTIFY_CENTER);
        y += dc.getFontHeight(font) + 5;
        if (_isRecording) {
            dc.drawText(_width / 2, y, font, "rec", Graphics.TEXT_JUSTIFY_CENTER);
            y += dc.getFontHeight(font) + 5;
        }
    }

    public function setRecordingStatus(isRecording as Boolean) {
        _isRecording = isRecording;
    }
}
