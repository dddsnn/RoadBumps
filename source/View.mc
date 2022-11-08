import Toybox.Graphics;
import Toybox.Lang;
import Toybox.Timer;
import Toybox.WatchUi;

class View extends WatchUi.View {
    private var _dataTimer as Timer.Timer;
    private var _history as AccelerationHistory;

    public function initialize(history as AccelerationHistory) {
        View.initialize();
        _dataTimer = new Timer.Timer();
        _history = history;
    }

    public function onLayout(dc as Dc) {
        _dataTimer.start(method(:refresh), 1000, true);
    }

    public function refresh() as Void {
        WatchUi.requestUpdate();
    }

    public function onUpdate(dc as Dc) as Void {
        var writer = new LineWriter(dc);
        writer.write(Lang.format("sample rate: $1$", [_history.getSampleRate()]), Graphics.FONT_XTINY);
        writer.write(Lang.format("last Y: $1$", [_history.getLastY()]), Graphics.FONT_MEDIUM);
    }
}

class LineWriter {
    private var _dc as Graphics.Dc;
    private var _center as Lang.Number;
    private var _y as Lang.Number = 5;

    public function initialize(dc as Graphics.Dc) {
        _dc = dc;
        _center = dc.getWidth() / 2;
        _dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_BLACK);
        _dc.clear();
    }

    public function write(line as String, font as Graphics.FontType) {
        _dc.drawText(_center, _y, font, line, Graphics.TEXT_JUSTIFY_CENTER);
        _y += _dc.getFontHeight(font) + 5;
    }
}
