//
// Copyright 2015-2021 by Garmin Ltd. or its subsidiaries.
// Subject to Garmin SDK License Agreement and Wearables
// Application Developer Agreement.
//

import Toybox.Application;
import Toybox.Lang;
import Toybox.WatchUi;

class BumpRecorderApp extends Application.AppBase {
    public function initialize() {
        AppBase.initialize();
    }

    public function onStart(state as Dictionary?) as Void {
    }

    public function onStop(state as Dictionary?) as Void {
    }

    public function getInitialView() as Array<Views or InputDelegates>? {
        var mainView = new $.BumpRecorderView();
        var viewDelegate = new $.BumpRecorderDelegate(mainView);
        return [mainView, viewDelegate] as Array<Views or InputDelegates>;
    }
}
