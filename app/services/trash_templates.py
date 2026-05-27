import random
from collections import defaultdict

TEMPLATES = {
    "BLOWOUT_ALERT": [
        "Incident logged. {user}'s {team} are reportedly down bad. Context: {context}.",
        "FraudWatch has received a blowout report involving {user} and the {team}. The group may proceed.",
        "A witness has submitted evidence that {team} are getting cooked. {user}, please respond.",
        "Emergency group meeting: {user}'s {team} are in a serious situation. Context on file: {context}.",
        "{user} chose {team} voluntarily. The group has questions about that decision.",
        "FraudWatch Alert: structural failure detected in {team} fandom. {user} has been summoned.",
        "Down bad. {user}'s {team} have entered the witness protection program.",
    ],
    "CHOKED_LEAD": [
        "Incident logged: {team} allegedly surrendered a lead. {user}, the floor is yours.",
        "A collapse report has been filed. Prior condition: {context}. Current dignity: unclear.",
        "FraudWatch has opened an inquiry into {team}'s lead management.",
        "{user}'s {team} had it. They no longer have it. A formal report has been submitted.",
        "Collapse detection active. {user} is requested to explain what happened to {team}.",
        "{team} built something and dismantled it themselves. {user} witnessed all of it.",
        "The lead is gone. FraudWatch has documented this in full. {user} has been notified.",
    ],
    "FRAUD_WATCH": [
        "Fraud Watch activated for {user} and the {team}.",
        "A group member has formally questioned {user}'s team selection.",
        "This report does not confirm fraud. It merely strongly suggests it.",
        "FraudWatch has placed {user}'s {team} under official observation.",
        "{team} have been flagged. {user}, you have 24 hours to explain the tape.",
        "An official investigation has been opened. Subject: {team}. Fan of record: {user}.",
        "{user}, the committee has reviewed the footage. {team} have questions to answer.",
    ],
    "FINAL_LOSS": [
        "Final: {team} lost. {user} has 24 hours to issue a statement.",
        "The scoreboard is final. Unfortunately, so is the slander.",
        "{team} lost, and {user}'s fan credibility has been updated accordingly.",
        "It's over. {user}'s {team} concluded their business on the losing end. Context: {context}.",
        "Final score recorded. {user}'s {team} did not win. The receipt is being prepared.",
        "{user}, the game is final. The group is ready to begin proceedings.",
        "Result logged. {team} lost. {user}'s defense window is now open.",
    ],
    "PLAYOFF_COLLAPSE": [
        "{user}'s {team} were leading. They are no longer leading. This is a postseason.",
        "Playoff meltdown in progress. {user}, please stand by for the thread.",
        "{team} built something and then dismantled it themselves. {user} witnessed this.",
        "FraudWatch Playoff Alert: {team} have surrendered their advantage. Context: {context}.",
        "The lead is gone. The dignity is gone. {user}'s {team} in the playoffs, everyone.",
        "Postseason collapse report filed. The evidence has been preserved.",
        "{user}, this is a playoff incident. The group will not let this pass quietly.",
    ],
    "UPSET_ALERT": [
        "{user}'s {team} are losing to a team they were supposed to beat. This is being archived.",
        "FraudWatch detected an upset in progress. {user}, we are watching.",
        "{team} are getting beaten by someone they shouldn't be losing to. {user}, please explain.",
        "An upset is happening. {user}'s {team} are the ones getting upset.",
        "The expected outcome is not occurring. {user}'s {team} have other ideas. Context: {context}.",
        "Upset alert filed. {team} are performing below the expectations set by {user}.",
        "This was supposed to be a comfortable win. It is not. {user} has been notified.",
    ],
    "DISASTER_QUARTER": [
        "{team} just gave up a catastrophic stretch. {user}'s morale has been updated accordingly.",
        "FraudWatch recorded a historically bad period from {team}. {user}, you watched this.",
        "{user}'s {team} just had that kind of quarter. The group has taken note.",
        "Damage report: {team} collapsed and {user} was there for all of it. Context: {context}.",
        "{team} had a meltdown. {user}'s faith will be tested by this group.",
        "Quarter of record: concerning. {user} is required to account for {team}'s performance.",
        "A disaster quarter has been formally reported. {user}, the thread is open.",
    ],
    "SHUTOUT_RISK": [
        "{team} have zero points. {user}, the scoreboard is speaking.",
        "FraudWatch reporting: {user}'s {team} are scoreless. This is being logged.",
        "{user}, your {team} have been unable to score. The group has noticed.",
        "Scoreless report filed. {team}: 0. {user}'s spirit: also under review.",
        "Halftime update: {team} have not scored. {user} has not commented. Both are concerning.",
        "{user}'s {team} are yet to appear on the scoreboard. Context: {context}.",
        "This is a shutout risk incident. {user} is advised to address the group.",
    ],
    "RIVAL_LOSS": [
        "Rival incident filed. {user}'s {team} lost to someone they should not have lost to.",
        "FraudWatch has noted a rivalry result that will require {user} to explain themselves.",
        "{team} lost to a rival. {user} is requested to account for this outcome.",
        "The rivalry result is logged. {user}'s credibility in this group is under review.",
        "{user}, your team lost to the wrong team. Context: {context}. The group is aware.",
        "Rival loss report submitted. {team} had one job. {user} is expected to respond.",
        "A rivalry incident has occurred. FraudWatch has officially opened {user}'s file.",
    ],
    "PREMATURE_SLANDER": [
        "A PREMATURE_SLANDER incident has been filed. This report may age poorly.",
        "FraudWatch has received a report. The target is {user}. The claim is noted.",
        "This report is on the record. If {team} performs well, this document will be cited.",
        "Incident report filed against {user}. The group will determine if this was warranted.",
        "{user} has been reported before anything definitive happened. The group is watching.",
        "A report has been submitted. Whether it is justified remains to be seen. Stay vigilant.",
        "FraudWatch has logged this report. Premature slander carries its own risks.",
    ],
    "REDEMPTION_WIN": [
        "Update: this slander may have aged poorly.",
        "{user} survives FraudWatch review. Several haters may need to apologize.",
        "The group acted too soon. Receipts have been preserved for the reporters.",
        "{user}'s {team} have redeemed themselves. Attackers, please update your takes.",
        "Correction: {team} won. {user} will be accepting apologies in the thread.",
        "FraudWatch Update: {user}'s {team} survived. The shame goes to those who doubted.",
        "Redemption event logged. The group acted with confidence, not accuracy.",
    ],
    "RIVAL_WINNING": [
        "Rival update: not only is {team} losing, but the rival is winning. {user} is having a day.",
        "{user}, the rival would like to formally introduce themselves via the scoreboard.",
        "FraudWatch calculates that {user}'s evening has just gotten statistically worse.",
        "The rival is up. {team} is down. {user}, the floor is yours.",
        "Both things are happening simultaneously. {user} is not having a good time.",
    ],
    "ELIMINATION_RISK": [
        "{user}'s {team} are on the edge. One more loss and the season becomes a documentary.",
        "FraudWatch is monitoring {team}'s playoff status closely. So is everyone in this group.",
        "{user}, your {team} are statistically one foot out the door. Two feet, maybe.",
        "Elimination watch activated. {team} are performing in ways that concern us all.",
        "{team} are this close to ending the season early. {user} has been notified.",
    ],
}


def pick_template(trigger_type, **kwargs):
    options = TEMPLATES.get(trigger_type, TEMPLATES["FRAUD_WATCH"])
    template = random.choice(options)
    safe = defaultdict(str, kwargs)
    return template.format_map(safe)
