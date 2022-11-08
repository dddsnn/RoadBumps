import Toybox.Graphics;
import Toybox.Timer;
import Toybox.WatchUi;

class View extends WatchUi.View {
    private var _dataTimer as Timer.Timer;
    private var _history as AccelerationHistory;
    private var _width = 0;
    private var _height = 0;

    public function initialize(history as AccelerationHistory) {
        View.initialize();
        _dataTimer = new Timer.Timer();
        _history = history;
    }

    public function onLayout(dc as Dc) {
        _width = dc.getWidth();
        _height = dc.getHeight();
        _dataTimer.start(method(:refresh), 100, true);
    }

    public function refresh() as Void {
        WatchUi.requestUpdate();
    }

    public function onUpdate(dc as Dc) as Void {
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_BLACK);
        dc.clear();
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
        dc.drawText(_width / 2, 3, Graphics.FONT_TINY, _history.get(), Graphics.TEXT_JUSTIFY_CENTER);
    }
}
