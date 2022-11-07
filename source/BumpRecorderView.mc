//
// Copyright 2015-2021 by Garmin Ltd. or its subsidiaries.
// Subject to Garmin SDK License Agreement and Wearables
// Application Developer Agreement.
//

import Toybox.Graphics;
import Toybox.Lang;
import Toybox.Math;
import Toybox.Sensor;
import Toybox.Timer;
import Toybox.WatchUi;

class BumpRecorderView extends WatchUi.View {
    private var _dataTimer as Timer.Timer?;
    private var _accel as Array<Float>;
    private var _width = 0;
    private var _height = 0;

    public function initialize() {
        View.initialize();
        _accel = new Array<Float>[3];
    }

    public function onLayout(dc as Dc) {
        _width = dc.getWidth();
        _height = dc.getHeight();
        _dataTimer = new Timer.Timer();
        _dataTimer.start(method(:timerCallback), 100, true);
    }

    public function onShow() as Void {
    }

    public function onUpdate(dc as Dc) as Void {
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_BLACK);
        dc.clear();
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
        if (_accel != null) {
            dc.drawText(_width / 2,  3, Graphics.FONT_TINY, "Ax = " + _accel[0], Graphics.TEXT_JUSTIFY_CENTER);
            dc.drawText(_width / 2, 23, Graphics.FONT_TINY, "Ay = " + _accel[1], Graphics.TEXT_JUSTIFY_CENTER);
            dc.drawText(_width / 2, 43, Graphics.FONT_TINY, "Az = " + _accel[2], Graphics.TEXT_JUSTIFY_CENTER);
        } else {
            dc.drawText(_width / 2, 3, Graphics.FONT_TINY, "no Accel", Graphics.TEXT_JUSTIFY_CENTER);
        }
    }

    public function timerCallback() as Void {
        var info = Sensor.getInfo();
        if (info has :accel && info.accel != null) {
            _accel = info.accel as Array<Float>;
            WatchUi.requestUpdate();
        }
    }

    public function onHide() as Void {
    }
}
