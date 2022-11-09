import Toybox.Graphics;
import Toybox.Lang;
import Toybox.Timer;
import Toybox.WatchUi;

public function min(a, b) {
    if (a <= b) {
        return a;
    }
    return b;
}

class View extends WatchUi.View {
    private var _dataTimer as Timer.Timer;
    private var _history as AccelerationHistory;
    private var _width as Lang.Number;
    private var _height as Lang.Number;
    private var _graphOffset as Lang.Number;

    public function initialize() {
        View.initialize();
        _dataTimer = new Timer.Timer();
        _history = new AccelerationHistory(100);
    }

    public function onLayout(dc as Dc) {
        _width = dc.getWidth();
        _height = dc.getHeight();
        _graphOffset = 50;
        _dataTimer.start(method(:refresh), 1000, true);
    }

    public function refresh() as Void {
        WatchUi.requestUpdate();
    }

    public function onUpdate(dc as Dc) as Void {
        resetColors(dc);
        dc.clear();
        drawInfo(dc);
        drawGraph(dc);
    }

    private function resetColors(dc as Dc) as Void {
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_BLACK);
    }

    private function drawInfo(dc as Graphics.Dc) {
        var y = 5;
        var font = Graphics.FONT_XTINY;
        dc.drawText(_width / 2, y, font, Lang.format("sample rate: $1$", [_history.getSampleRate()]), Graphics.TEXT_JUSTIFY_CENTER);
        y += dc.getFontHeight(font) + 5;
    }

    private function drawGraph(dc as Graphics.Dc) {
        var barWidth = 3;
        var numBars = _width / barWidth;
        var graphHeight = _height - _graphOffset;
        var centerY = (graphHeight / 2) + _graphOffset;
        dc.setColor(Graphics.COLOR_RED, Graphics.COLOR_BLACK);
        dc.fillRectangle(0, centerY, _width, 1);
        resetColors(dc);
        var reversedHistory = _history.reversed();
        for (var i = 0; i < numBars; i++) {
            var value = reversedHistory.next();
            if (value == null) {
                break;
            }
            var barHeight = (value * (graphHeight / 2)).abs() / 2000;
            barHeight = min(barHeight, graphHeight / 2);
            var y = centerY;
            if (value > 0) {
                y -= barHeight;
            }
            dc.fillRectangle(_width - ((i + 1) * barWidth), y, barWidth, barHeight);
        }
    }
}
