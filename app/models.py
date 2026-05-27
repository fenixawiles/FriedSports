import uuid
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


def now_utc():
    return datetime.now(timezone.utc)


def generate_uid():
    return str(uuid.uuid4())


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.String(36), unique=True, nullable=False, default=generate_uid, index=True)
    display_name = db.Column(db.String(64), nullable=False)       # username
    first_name = db.Column(db.String(64), nullable=True)
    last_name = db.Column(db.String(64), nullable=True)
    # "username" → show display_name, "real_name" → show first + last
    display_preference = db.Column(db.String(16), nullable=False, default="username")
    has_completed_profile = db.Column(db.Boolean, nullable=False, default=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    avatar_url = db.Column(db.String(256))
    role = db.Column(db.String(16), nullable=False, default="user")  # "user", "admin"
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

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_favorite_team(self, league):
        uft = self.favorite_teams.filter_by(league=league).first()
        return uft.team if uft else None

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
        return self.messages.filter_by(message_type="user").count()


class GameThreadMessage(db.Model):
    __tablename__ = "game_thread_messages"

    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.Integer, db.ForeignKey("game_threads.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    message_type = db.Column(db.String(16), nullable=False, default="user")  # system, user
    body = db.Column(db.Text, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)

    author = db.relationship("User", foreign_keys=[user_id])
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
    reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)

    reporter = db.relationship("User")


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
