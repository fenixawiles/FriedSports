from flask import Blueprint, jsonify, render_template

legal_bp = Blueprint("legal", __name__)


@legal_bp.route("/privacy")
def privacy():
    return render_template("legal/privacy.html")


@legal_bp.route("/terms")
def terms():
    return render_template("legal/terms.html")


@legal_bp.route("/.well-known/apple-app-site-association")
def apple_app_site_association():
    """
    Universal Links — allows invite links to open in the native iOS app.
    Update <TEAM_ID>.<BUNDLE_ID> after setting up your Apple Developer account.
    Bundle ID: com.friedsports.app
    """
    data = {
        "applinks": {
            "apps": [],
            "details": [
                {
                    "appID": "TEAMID.com.friedsports.app",
                    "paths": [
                        "/groups/join/*",
                        "/dashboard",
                        "/groups/*",
                        "/threads/*",
                    ]
                }
            ]
        }
    }
    response = jsonify(data)
    response.headers["Content-Type"] = "application/json"
    return response
