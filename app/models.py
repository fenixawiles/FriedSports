import random as _random
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


def now_utc():
    return datetime.now(timezone.utc)


def generate_uid():
    """FS-XXXXXX where X is a random digit (0-9)."""
    return 'FS-' + ''.join(_random.choices('0123456789', k=6))


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.String(12), unique=True, nullable=False, default=generate_uid, index=True)
    display_name = db.Column(db.String(64), nullable=False)       # username
    first_name = db.Column(db.String(64), nullable=True)
    last_name = db.Column(db.String(64), nullable=True)
    # "username" → show display_name, "real_name" → show first + last
    display_preference = db.Column(db.String(16), nullable=False, default="username")
    has_completed_profile = db.Column(db.Boolean, nullable=False, default=False)
    email_verified = db.Column(db.Boolean, nullable=False, default=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    avatar_url = db.Column(db.String(256))
    role = db.Column(db.String(16), nullable=False, default="user")  # "user", "admin"
    last_active_at = db.Column(db.DateTime(timezone=True), nullable=True)
    # Timestamp the user agreed to the Terms / community guidelines (EULA).
    # Required for App Store UGC compliance — set at signup.
    agreed_to_terms_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)
    updated_at = db.Column(db.DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    favorite_teams = db.relationship("UserFavoriteTeam", backref="user", lazy="dynamic")
    group_memberships = db.relationship("GroupMember", backref="user", lazy="dynamic")

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def shown_name(self):
        """The name to display publicly — respects display_preference."""
        if (self.display_preference == "real_name"
                and self.first_name and self.last_name):
            return f"{self.first_name} {self.last_name}"
        return self.display_name

    @property
    def initials(self):
        """Up to two uppercase initials for avatar circles."""
        name = self.shown_name or ""
        parts = name.split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        return name[:2].upper() if name else "?"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_favorite_team(self, league):
        uft = self.favorite_teams.filter_by(league=league).first()
        return uft.team if uft else None

    # ── Blocking ──────────────────────────────────────────────────────────────
    def has_blocked(self, other_id):
        """True if this user has blocked other_id."""
        return BlockedUser.query.filter_by(
            blocker_id=self.id, blocked_id=other_id
        ).count() > 0

    def blocked_user_ids(self):
        """Set of user ids this user has blocked."""
        return {
            b.blocked_id
            for b in BlockedUser.query.filter_by(blocker_id=self.id).all()
        }

    def hidden_user_ids(self):
        """Set of user ids hidden from this user in BOTH directions —
        people I blocked plus people who blocked me. Used to filter content
        and search so a block is mutually invisible."""
        ids = set()
        rows = BlockedUser.query.filter(
            db.or_(
                BlockedUser.blocker_id == self.id,
                BlockedUser.blocked_id == self.id,
            )
        ).all()
        for b in rows:
            ids.add(b.blocked_id if b.blocker_id == self.id else b.blocker_id)
        return ids

    def __repr__(self):
        return f"<User {self.display_name}>"


class AdminAuditLog(db.Model):
    __tablename__ = "admin_audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    target_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(64), nullable=False)   # e.g. "change_email"
    details = db.Column(db.Text, nullable=True)          # human-readable summary
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)

    admin = db.relationship("User", foreign_keys=[admin_id])
    target_user = db.relationship("User", foreign_keys=[target_user_id])


class Team(db.Model):
    __tablename__ = "teams"

    id = db.Column(db.Integer, primary_key=True)
    league = db.Column(db.String(8), nullable=False, index=True)
    name = db.Column(db.String(64), nullable=False)
    abbreviation = db.Column(db.String(8), nullable=False)
    city = db.Column(db.String(64))
    logo_url = db.Column(db.String(256))
    primary_color = db.Column(db.String(8), default="#333333")
    secondary_color = db.Column(db.String(8), default="#ffffff")

    def __repr__(self):
        return f"<Team {self.league} {self.name}>"


class UserFavoriteTeam(db.Model):
    __tablename__ = "user_favorite_teams"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    league = db.Column(db.String(8), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)
    updated_at = db.Column(db.DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    __table_args__ = (db.UniqueConstraint("user_id", "league", name="uq_user_league_team"),)

    team = db.relationship("Team")


class Group(db.Model):
    __tablename__ = "groups"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    league_scope = db.Column(db.String(8), nullable=False, default="MULTI")  # NBA, NFL, MULTI
    privacy = db.Column(db.String(20), nullable=False, default="private")  # private, public_readonly
    invite_code = db.Column(db.String(16), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)
    updated_at = db.Column(db.DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    owner = db.relationship("User", foreign_keys=[owner_id])
    members = db.relationship("GroupMember", backref="group", lazy="dynamic")
    threads = db.relationship("GameThread", backref="group", lazy="dynamic")

    def get_member(self, user_id):
        return self.members.filter_by(user_id=user_id).first()

    def is_member(self, user_id):
        return self.members.filter_by(user_id=user_id).count() > 0


class GroupMember(db.Model):
    __tablename__ = "group_members"

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    role = db.Column(db.String(16), nullable=False, default="member")  # owner, admin, member
    joined_at = db.Column(db.DateTime(timezone=True), default=now_utc)
    mute_notifications = db.Column(db.Boolean, default=False)
    trash_talk_score = db.Column(db.Integer, default=0)
    shame_score = db.Column(db.Integer, default=0)
    bragging_rights_score = db.Column(db.Integer, default=0)
    defense_score = db.Column(db.Integer, default=0)
    reporter_score = db.Column(db.Integer, default=0)

    __table_args__ = (db.UniqueConstraint("group_id", "user_id", name="uq_group_user"),)


class IncidentReport(db.Model):
    __tablename__ = "incident_reports"

    id = db.Column(db.Integer, primary_key=True)
    reporter_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), nullable=False)
    target_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    target_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    league = db.Column(db.String(8), nullable=False)
    incident_type = db.Column(db.String(32), nullable=False)
    severity = db.Column(db.Integer, nullable=False, default=3)
    reported_score_text = db.Column(db.String(120), nullable=True)
    description = db.Column(db.Text, nullable=True)
    # active | confirmed | disputed | dismissed | redeemed
    status = db.Column(db.String(16), nullable=False, default="active")
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)
    updated_at = db.Column(db.DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    reporter = db.relationship("User", foreign_keys=[reporter_user_id])
    target_user = db.relationship("User", foreign_keys=[target_user_id])
    target_team = db.relationship("Team")
    group = db.relationship("Group")


class Game(db.Model):
    __tablename__ = "games"

    id = db.Column(db.Integer, primary_key=True)
    external_game_id = db.Column(db.String(64), unique=True, nullable=False)
    league = db.Column(db.String(8), nullable=False)
    home_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    away_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    start_time = db.Column(db.DateTime(timezone=True))
    status = db.Column(db.String(16), default="scheduled")  # scheduled, live, final
    period = db.Column(db.Integer, default=1)
    clock = db.Column(db.String(16), default="12:00")
    home_score = db.Column(db.Integer, default=0)
    away_score = db.Column(db.Integer, default=0)
    max_home_lead = db.Column(db.Integer, default=0)
    max_away_lead = db.Column(db.Integer, default=0)
    last_checked_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)
    updated_at = db.Column(db.DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    home_team = db.relationship("Team", foreign_keys=[home_team_id])
    away_team = db.relationship("Team", foreign_keys=[away_team_id])
    events = db.relationship("GameEvent", backref="game", lazy="dynamic",
                             foreign_keys="GameEvent.game_id")

    def current_margin(self):
        return abs(self.home_score - self.away_score)

    def leading_team_id(self):
        if self.home_score > self.away_score:
            return self.home_team_id
        elif self.away_score > self.home_score:
            return self.away_team_id
        return None

    def losing_team_id(self):
        if self.home_score < self.away_score:
            return self.home_team_id
        elif self.away_score < self.home_score:
            return self.away_team_id
        return None


class GameEvent(db.Model):
    __tablename__ = "game_events"

    id = db.Column(db.Integer, primary_key=True)
    # Nullable: set for automated game events, None for user-reported incidents
    game_id = db.Column(db.Integer, db.ForeignKey("games.id"), nullable=True)
    # Nullable: set for user-reported incidents, None for automated events
    incident_report_id = db.Column(db.Integer, db.ForeignKey("incident_reports.id"), nullable=True)
    trigger_type = db.Column(db.String(32), nullable=False)
    target_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    severity = db.Column(db.Integer, default=1)
    title = db.Column(db.String(256))
    body = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)
    resolved_at = db.Column(db.DateTime(timezone=True))

    target_team = db.relationship("Team")
    group_triggers = db.relationship("GroupTrigger", backref="game_event", lazy="dynamic")
    incident_report = db.relationship(
        "IncidentReport",
        foreign_keys=[incident_report_id],
        uselist=False,
    )


class GroupTrigger(db.Model):
    __tablename__ = "group_triggers"

    id = db.Column(db.Integer, primary_key=True)
    game_event_id = db.Column(db.Integer, db.ForeignKey("game_events.id"), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), nullable=False)
    target_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)

    __table_args__ = (
        db.UniqueConstraint("game_event_id", "group_id", "target_user_id", name="uq_trigger_group_user"),
    )

    target_user = db.relationship("User")
    threads = db.relationship("GameThread", backref="group_trigger", lazy="dynamic")


class GameThread(db.Model):
    __tablename__ = "game_threads"

    id = db.Column(db.Integer, primary_key=True)
    group_trigger_id = db.Column(db.Integer, db.ForeignKey("group_triggers.id"), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), nullable=False)
    target_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    target_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    title = db.Column(db.String(256))
    status = db.Column(db.String(16), default="active")  # active, closed
    hot_score = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)
    updated_at = db.Column(db.DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    target_user = db.relationship("User", foreign_keys=[target_user_id])
    target_team = db.relationship("Team", foreign_keys=[target_team_id])
    messages = db.relationship("GameThreadMessage", backref="thread", lazy="dynamic",
                               order_by="GameThreadMessage.created_at")
    receipts = db.relationship("Receipt", backref="thread", lazy="dynamic")

    def has_replied(self, user_id):
        return self.messages.filter(
            GameThreadMessage.user_id == user_id,
            GameThreadMessage.message_type == "user"
        ).count() > 0

    def target_has_replied(self):
        return self.has_replied(self.target_user_id)

    def reply_count(self):
        return self.messages.filter_by(message_type="user", is_deleted=False).count()

    def last_reply(self):
        return (self.messages
                .filter_by(is_deleted=False)
                .order_by(GameThreadMessage.created_at.desc())
                .first())

    def unread_count_for(self, user_id):
        """Messages posted after the user's read watermark (all if never read)."""
        read = ThreadRead.query.filter_by(user_id=user_id, thread_id=self.id).first()
        q = self.messages.filter_by(is_deleted=False)
        if read:
            q = q.filter(GameThreadMessage.created_at > read.last_read_at)
        return q.count()

    def vote_counts(self):
        from sqlalchemy import func
        rows = (db.session.query(ThreadVote.vote_type, func.count(ThreadVote.id))
                .filter_by(thread_id=self.id)
                .group_by(ThreadVote.vote_type)
                .all())
        counts = {"confirm": 0, "dismiss": 0, "redeem": 0}
        for vtype, cnt in rows:
            counts[vtype] = cnt
        return counts

    def user_vote(self, user_id):
        v = ThreadVote.query.filter_by(thread_id=self.id, user_id=user_id).first()
        return v.vote_type if v else None


class GameThreadMessage(db.Model):
    __tablename__ = "game_thread_messages"

    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.Integer, db.ForeignKey("game_threads.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    message_type = db.Column(db.String(16), nullable=False, default="user")  # system, user
    body = db.Column(db.Text, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False)
    # Optional "reply to" reference for native quote-replies. Nullable; no DB-level
    # cascade — an orphaned reference simply renders no quote.
    reply_to_id = db.Column(db.Integer, db.ForeignKey("game_thread_messages.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)

    author = db.relationship("User", foreign_keys=[user_id])
    reply_to = db.relationship("GameThreadMessage", remote_side=[id],
                               foreign_keys=[reply_to_id], uselist=False)
    reactions = db.relationship("MessageReaction", backref="message", lazy="select")
    reports = db.relationship("MessageReport", backref="message", lazy="select")

    def reaction_counts(self):
        counts = {}
        for r in self.reactions:
            counts[r.reaction_type] = counts.get(r.reaction_type, 0) + 1
        return counts

    def user_reaction(self, user_id):
        return [r.reaction_type for r in self.reactions if r.user_id == user_id]


class MessageReaction(db.Model):
    __tablename__ = "message_reactions"

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey("game_thread_messages.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    reaction_type = db.Column(db.String(16), nullable=False)  # laugh, cook, fraud, receipt
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)

    __table_args__ = (
        db.UniqueConstraint("message_id", "user_id", "reaction_type", name="uq_reaction"),
    )

    user = db.relationship("User")


class MessageReport(db.Model):
    __tablename__ = "message_reports"

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey("game_thread_messages.id"), nullable=False)
    reporter_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    category = db.Column(db.String(32), nullable=True)   # harassment | hate | spam | threat | other
    reason = db.Column(db.Text)
    # Moderation lifecycle — open until an admin actions it.
    status = db.Column(db.String(16), nullable=False, default="open",
                       server_default="open")            # open | resolved | dismissed
    resolution = db.Column(db.String(32), nullable=True) # message_deleted | user_warned | no_action
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)

    reporter = db.relationship("User", foreign_keys=[reporter_user_id])
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])

    CATEGORY_LABELS = {
        "harassment": "Harassment or bullying",
        "hate":       "Hate speech",
        "threat":     "Threat of harm",
        "spam":       "Spam",
        "other":      "Other",
    }

    @property
    def category_label(self):
        return self.CATEGORY_LABELS.get(self.category, self.category or "Unspecified")


class BlockedUser(db.Model):
    """One user blocking another. A block is mutually invisible — see
    User.hidden_user_ids(). Used for App Store UGC compliance."""
    __tablename__ = "blocked_users"

    id         = db.Column(db.Integer, primary_key=True)
    blocker_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    blocked_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)

    __table_args__ = (
        db.UniqueConstraint("blocker_id", "blocked_id", name="uq_blocked_user"),
    )

    blocker = db.relationship("User", foreign_keys=[blocker_id])
    blocked = db.relationship("User", foreign_keys=[blocked_id])


class Receipt(db.Model):
    __tablename__ = "receipts"

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("groups.id"), nullable=False)
    thread_id = db.Column(db.Integer, db.ForeignKey("game_threads.id"), nullable=False)
    target_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    target_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=False)
    title = db.Column(db.String(256))
    summary = db.Column(db.Text)
    final_score = db.Column(db.String(64))
    shame_points = db.Column(db.Integer, default=0)
    top_hater_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    public_slug = db.Column(db.String(16), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)

    group = db.relationship("Group")
    target_user = db.relationship("User", foreign_keys=[target_user_id])
    target_team = db.relationship("Team", foreign_keys=[target_team_id])
    top_hater = db.relationship("User", foreign_keys=[top_hater_user_id])


class DeviceToken(db.Model):
    """Push notification device tokens for iOS (APNs)."""
    __tablename__ = "device_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    token = db.Column(db.String(256), unique=True, nullable=False)
    platform = db.Column(db.String(8), nullable=False, default="ios")
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)
    updated_at = db.Column(db.DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    user = db.relationship("User", backref=db.backref("device_tokens", lazy="select"))


class LoginToken(db.Model):
    """Single-use tokens for email OTP sign-in and magic-link authentication."""
    __tablename__ = "login_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    purpose = db.Column(db.String(32), nullable=False)   # 'signin_code' | 'signup_code' | 'magic_link' | 'password_reset'
    code = db.Column(db.String(10), nullable=True)       # 8-digit OTP (signin_code/signup_code only)
    next_url = db.Column(db.String(512), nullable=True)  # redirect after magic link login
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)

    user = db.relationship("User", backref=db.backref("login_tokens", lazy="select"))

    @property
    def is_valid(self):
        return self.used_at is None and datetime.now(timezone.utc) < self.expires_at


def _generate_support_uid():
    """FS-XXXXXX where X is a random digit (0-9)."""
    return 'FS-' + ''.join(_random.choices('0123456789', k=6))


class SupportTicket(db.Model):
    """User-submitted support/bug reports with admin lifecycle management."""
    __tablename__ = "support_tickets"

    id          = db.Column(db.Integer, primary_key=True)
    uid         = db.Column(db.String(12), unique=True, nullable=False,
                            default=_generate_support_uid, index=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    subject     = db.Column(db.String(200), nullable=False)
    category    = db.Column(db.String(32), nullable=False, default="other")
    # bug | account | feature | billing | other
    description = db.Column(db.Text, nullable=False)
    status      = db.Column(db.String(16), nullable=False, default="received")
    # received | in_progress | resolved
    admin_note  = db.Column(db.Text, nullable=True)   # internal; shown to user as "Response"
    resolved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at  = db.Column(db.DateTime(timezone=True), default=now_utc)
    updated_at  = db.Column(db.DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    user = db.relationship("User", backref=db.backref("support_tickets", lazy="dynamic"))

    STATUS_LABELS = {
        "received":    "Received",
        "in_progress": "In Progress",
        "resolved":    "Resolved",
    }
    # Valid next statuses from each state; empty list = terminal
    NEXT_STATUSES = {
        "received":    ["in_progress", "resolved"],
        "in_progress": ["resolved"],
        "resolved":    [],
    }

    @property
    def is_resolved(self):
        return self.status == "resolved"

    @property
    def status_label(self):
        return self.STATUS_LABELS.get(self.status, self.status)


class Notification(db.Model):
    """In-app notifications — e.g. someone started a thread about your team."""
    __tablename__ = "notifications"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    type       = db.Column(db.String(32), nullable=False)    # 'thread_started'
    message    = db.Column(db.String(512), nullable=False)
    link_url   = db.Column(db.String(512), nullable=True)
    is_read    = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)

    user = db.relationship("User", backref=db.backref("notifications", lazy="dynamic"))


class FriendRequest(db.Model):
    """Friend request / friendship record. status='accepted' means an active friendship."""
    __tablename__ = "friend_requests"

    id           = db.Column(db.Integer, primary_key=True)
    from_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    to_user_id   = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    status       = db.Column(db.String(16), nullable=False, default="pending")
    # "pending" | "accepted" | "declined"
    created_at   = db.Column(db.DateTime(timezone=True), default=now_utc)
    updated_at   = db.Column(db.DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    from_user = db.relationship("User", foreign_keys=[from_user_id],
                                backref=db.backref("sent_friend_requests", lazy="dynamic"))
    to_user   = db.relationship("User", foreign_keys=[to_user_id],
                                backref=db.backref("received_friend_requests", lazy="dynamic"))

    __table_args__ = (
        db.UniqueConstraint("from_user_id", "to_user_id", name="uq_friend_request"),
    )


class ThreadRead(db.Model):
    """Per-user read watermark on a thread — drives unread counts."""
    __tablename__ = "thread_reads"

    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    thread_id    = db.Column(db.Integer, db.ForeignKey("game_threads.id"), nullable=False, index=True)
    last_read_at = db.Column(db.DateTime(timezone=True), nullable=False, default=now_utc)

    __table_args__ = (
        db.UniqueConstraint("user_id", "thread_id", name="uq_thread_read"),
    )


class ThreadVote(db.Model):
    """A group member's verdict on a thread: confirm | dismiss | redeem.
    One vote per (thread, user) — re-voting switches it, same vote removes it."""
    __tablename__ = "thread_votes"

    id         = db.Column(db.Integer, primary_key=True)
    thread_id  = db.Column(db.Integer, db.ForeignKey("game_threads.id"), nullable=False, index=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    vote_type  = db.Column(db.String(16), nullable=False)  # confirm | dismiss | redeem
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)

    __table_args__ = (
        db.UniqueConstraint("thread_id", "user_id", name="uq_thread_vote"),
    )

    user = db.relationship("User")


class ThreadUserState(db.Model):
    """Per-user view state on a thread: archive + local delete (history clear).

    Deletion is local to the user and never touches the shared message store:
    `cleared_at` hides every message at/before it FROM THIS USER only. A deleted
    thread sits in Recently Deleted; if a new message arrives after cleared_at it
    resurfaces in the user's list as a fresh thread (only the new messages)."""
    __tablename__ = "thread_user_states"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    thread_id  = db.Column(db.Integer, db.ForeignKey("game_threads.id"), nullable=False, index=True)
    cleared_at = db.Column(db.DateTime(timezone=True), nullable=True)   # hide msgs at/before this
    archived   = db.Column(db.Boolean, default=False, nullable=False)
    deleted    = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime(timezone=True), nullable=True)   # for 30-day purge window

    __table_args__ = (
        db.UniqueConstraint("user_id", "thread_id", name="uq_thread_user_state"),
    )


class ActivityEvent(db.Model):
    """Group activity feed — thread starts, replies, votes, joins."""
    __tablename__ = "activity_events"

    id         = db.Column(db.Integer, primary_key=True)
    group_id   = db.Column(db.Integer, db.ForeignKey("groups.id"), nullable=True, index=True)
    actor_id   = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    event_type = db.Column(db.String(32), nullable=False)  # thread_started | reply | vote | member_joined
    entity_id  = db.Column(db.Integer, nullable=True)      # thread_id or message_id
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc, index=True)

    actor = db.relationship("User")
