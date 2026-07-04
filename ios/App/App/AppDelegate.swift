import UIKit
import WebKit
import Capacitor

@UIApplicationMain
class AppDelegate: UIResponder, UIApplicationDelegate {

    var window: UIWindow?

    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        // Override point for customization after application launch.
        return true
    }

    func applicationWillResignActive(_ application: UIApplication) {
        // Sent when the application is about to move from active to inactive state. This can occur for certain types of temporary interruptions (such as an incoming phone call or SMS message) or when the user quits the application and it begins the transition to the background state.
        // Use this method to pause ongoing tasks, disable timers, and invalidate graphics rendering callbacks. Games should use this method to pause the game.
    }

    func applicationDidEnterBackground(_ application: UIApplication) {
        // Use this method to release shared resources, save user data, invalidate timers, and store enough application state information to restore your application to its current state in case it is terminated later.
        // If your application supports background execution, this method is called instead of applicationWillTerminate: when the user quits.
    }

    func applicationWillEnterForeground(_ application: UIApplication) {
        // Called as part of the transition from the background to the active state; here you can undo many of the changes made on entering the background.
    }

    func applicationDidBecomeActive(_ application: UIApplication) {
        // Restart any tasks that were paused (or not yet started) while the application was inactive. If the application was previously in the background, optionally refresh the user interface.
    }

    func applicationWillTerminate(_ application: UIApplication) {
        // Called when the application is about to terminate. Save data if appropriate. See also applicationDidEnterBackground:.
    }

    func application(_ app: UIApplication, open url: URL, options: [UIApplication.OpenURLOptionsKey: Any] = [:]) -> Bool {
        // Called when the app was launched with a url. Feel free to add additional processing here,
        // but if you want the App API to support tracking app url opens, make sure to keep this call
        return ApplicationDelegateProxy.shared.application(app, open: url, options: options)
    }

    func application(_ application: UIApplication, continue userActivity: NSUserActivity, restorationHandler: @escaping ([UIUserActivityRestoring]?) -> Void) -> Bool {
        // Called when the app was launched with an activity, including Universal Links.
        // Feel free to add additional processing here, but if you want the App API to support
        // tracking app url opens, make sure to keep this call
        return ApplicationDelegateProxy.shared.application(application, continue: userActivity, restorationHandler: restorationHandler)
    }

    // ── APNs push registration bridge ──────────────────────────────────────
    // @capacitor/push-notifications listens for these NotificationCenter posts;
    // without them Push.register() never resolves with a device token.
    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        NotificationCenter.default.post(name: .capacitorDidRegisterForRemoteNotifications, object: deviceToken)
    }

    func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: Error) {
        NotificationCenter.default.post(name: .capacitorDidFailToRegisterForRemoteNotifications, object: error)
    }

}

/// Root web view controller — re-enables native iOS elastic overscroll.
///
/// Capacitor's `CAPBridgeViewController` hard-sets `scrollView.bounces = false`
/// in `prepareWebView`, and there is NO capacitor.config option to change it.
/// That is why the packaged app never rubber-bands the way mobile Safari does —
/// CSS (`overscroll-behavior`, `-webkit-overflow-scrolling`) cannot re-enable a
/// `UIScrollView` whose `bounces` is off. `capacitorDidLoad()` runs right after
/// the web view is created, so it's the supported place to flip it back on.
///
/// - `bounces = true`: the document rubber-bands at the top/bottom of any
///   scrollable page, and overflow scrollers (the chat message list) bounce too.
/// - `alwaysBounceVertical` is left at its default (false) on purpose: a page
///   whose content fits the viewport exactly — the locked 100dvh chat shell —
///   must not bounce as a whole block; only its inner `.chat-window` scrolls and
///   bounces. Pages taller than the viewport still bounce because their content
///   exceeds the scroll-view bounds.
class MainViewController: CAPBridgeViewController, WKScriptMessageHandler {
    override func capacitorDidLoad() {
        super.capacitorDidLoad()
        webView?.scrollView.bounces = true

        // Paint the view BEHIND the web view the app color. When the keyboard
        // resizes the web-view frame, this backing view is what shows in the
        // briefly-exposed strip during the animation — without this it's the
        // system black, which is the "black corners around the keyboard". Default
        // to light; the fsTheme bridge below corrects it to the live theme.
        view.backgroundColor = MainViewController.color(fromHex: "#f2f2f7")

        // Theme-correct overscroll: the rubber-band region is painted by the
        // native layer (scrollView.backgroundColor / underPageBackgroundColor),
        // which Capacitor hard-codes to a single light color. The app's dark mode
        // is a web-only toggle (localStorage), so the native side can't know the
        // theme on its own. The web posts its current --bg-primary here whenever
        // the theme changes; we mirror it onto the scroll view so the bounce
        // matches light/dark instead of flashing the wrong color.
        // (Registered on the live content controller; the JS side is fully
        // guarded, so a missing handler is simply a no-op — never a regression.)
        // Retain cycle self<-controller<-webView<-self is benign: this is the
        // root view controller and lives for the whole app session.
        webView?.configuration.userContentController.add(self, name: "fsTheme")
        webView?.configuration.userContentController.add(self, name: "fsBounce")

        // Keyboard ride. With capacitor.config Keyboard.resize="none" the plugin
        // does NOT resize the web view (it only disables the default scroll-to-
        // input and fires its JS events). Instead we resize the web-view frame
        // ourselves, RIGHT NOW at keyboardWillChangeFrame (the start of the
        // keyboard animation) and on the keyboard's own duration + curve — so the
        // composer rides up with the keyboard instead of the plugin's
        // keyboardDuration+0.2s delayed snap.
        NotificationCenter.default.addObserver(
            self, selector: #selector(keyboardWillChangeFrame(_:)),
            name: UIResponder.keyboardWillChangeFrameNotification, object: nil)
    }

    @objc private func keyboardWillChangeFrame(_ note: Notification) {
        guard let wv = webView,
              let info = note.userInfo,
              let end = (info[UIResponder.keyboardFrameEndUserInfoKey] as? NSValue)?.cgRectValue,
              let dur = info[UIResponder.keyboardAnimationDurationUserInfoKey] as? Double,
              let curveN = info[UIResponder.keyboardAnimationCurveUserInfoKey] as? UInt,
              let win = view.window else { return }
        let screen = win.bounds
        // How much the keyboard overlaps the window from the bottom (0 = hidden).
        let overlap = max(0, screen.maxY - end.minY)
        let target = CGRect(x: wv.frame.origin.x, y: wv.frame.origin.y,
                            width: screen.width - wv.frame.origin.x,
                            height: screen.height - wv.frame.origin.y - overlap)
        let opts = UIView.AnimationOptions(rawValue: curveN << 16).union(.beginFromCurrentState)
        UIView.animate(withDuration: dur > 0 ? dur : 0.25, delay: 0, options: opts,
                       animations: { wv.frame = target })
    }

    func userContentController(_ userContentController: WKUserContentController,
                               didReceive message: WKScriptMessage) {
        // Per-page document bounce: "0" on chat pages (so the fixed UI can't be
        // dragged by overscroll), "1" elsewhere. The inner .chat-window keeps its
        // own elastic bounce regardless.
        if message.name == "fsBounce" {
            let on = (message.body as? String) == "1"
            let wv = webView
            DispatchQueue.main.async { wv?.scrollView.bounces = on }
            return
        }
        guard message.name == "fsTheme",
              let hex = message.body as? String,
              let color = MainViewController.color(fromHex: hex) else { return }
        let wv = webView
        DispatchQueue.main.async {
            wv?.backgroundColor = color
            wv?.scrollView.backgroundColor = color
            // Backing view + window so the keyboard-resize strip matches the theme.
            self.view.backgroundColor = color
            self.view.window?.backgroundColor = color
            if #available(iOS 15.0, *) { wv?.underPageBackgroundColor = color }
        }
    }

    /// Parse a "#RRGGBB" string into an opaque UIColor. Returns nil on anything
    /// it doesn't recognize so a bad value just leaves the current color intact.
    private static func color(fromHex hex: String) -> UIColor? {
        var s = hex.trimmingCharacters(in: .whitespacesAndNewlines)
        if s.hasPrefix("#") { s.removeFirst() }
        guard s.count == 6, let v = UInt32(s, radix: 16) else { return nil }
        return UIColor(red:   CGFloat((v >> 16) & 0xFF) / 255.0,
                       green: CGFloat((v >>  8) & 0xFF) / 255.0,
                       blue:  CGFloat( v        & 0xFF) / 255.0,
                       alpha: 1.0)
    }
}
