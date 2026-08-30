from app.models.ai import AI_INTERACTION_STATUSES, AiInteraction
from app.models.ai_config import AiFeatureConfig
from app.models.appearance import BackdropSetting
from app.models.audio import AudioAsset
from app.models.chat import CHAT_ROLES, CoachConversation, CoachMessage
from app.models.coach import COACH_STATUSES, CoachExplanation, CoachFeedback
from app.models.dictation import (
    DictationAttempt,
    DictationItem,
    DictationSection,
    DictationStory,
    DictationTopic,
)
from app.models.encounter import Encounter, EncounterSetting
from app.models.health import HealthSample
from app.models.identity import IDENTITY_PROVIDERS, UserIdentity
from app.models.image import ImageAsset
from app.models.knowledge import KnowledgeChunk
from app.models.labels import QuestionLabel, QuestionSetLabel
from app.models.pet import EggSetting, PetlandMap, PetOwned, PetSpecies, PetState
from app.models.practice import (
    Attempt,
    AttemptItem,
    AttemptPart,
    PracticeTest,
    PracticeTestQuestion,
    Question,
    QuestionOption,
    QuestionSet,
    TestCollection,
)
from app.models.profile import UserProfile
from app.models.progression import (
    BADGE_ICONS,
    BADGE_METRICS,
    DAILY_TASK_KINDS,
    FRAME_TONES,
    XP_SOURCES,
    BadgeRule,
    DailyTaskSlot,
    FrameTier,
    LevelTier,
    ProgressionSetting,
    UserBadge,
    XpEvent,
)
from app.models.ruby import RubyEvent, RubyRule
from app.models.scoring import ScoreConversion, ScoreScale
from app.models.topic import Topic
from app.models.user import User
from app.models.vocabulary import (
    VocabularyAudio,
    VocabularyCollection,
    VocabularyCollectionItem,
    VocabularyEntry,
    VocabularyReviewLog,
    VocabularyReviewState,
    VocabularyTopic,
    VocabularyTopicSession,
)

# Every model must be reachable from here: this is the single import that
# registers the tables on Base.metadata for app.main, alembic/env.py and the test
# fixture alike. A model missing from this list produces "no such table" in tests
# and an empty autogenerate diff in Alembic.
__all__ = [
    "IDENTITY_PROVIDERS",
    "UserIdentity",
    "BADGE_ICONS",
    "BADGE_METRICS",
    "DAILY_TASK_KINDS",
    "FRAME_TONES",
    "XP_SOURCES",
    "BadgeRule",
    "DailyTaskSlot",
    "FrameTier",
    "LevelTier",
    "ProgressionSetting",
    "UserBadge",
    "XpEvent",
    "AI_INTERACTION_STATUSES",
    "AiFeatureConfig",
    "AiInteraction",
    "Attempt",
    "AttemptItem",
    "CHAT_ROLES",
    "COACH_STATUSES",
    "AttemptPart",
    "CoachConversation",
    "CoachExplanation",
    "CoachMessage",
    "CoachFeedback",
    "AudioAsset",
    "BackdropSetting",
    "DictationAttempt",
    "DictationItem",
    "DictationSection",
    "DictationStory",
    "DictationTopic",
    "ImageAsset",
    "KnowledgeChunk",
    "PracticeTest",
    "PracticeTestQuestion",
    "EggSetting",
    "Encounter",
    "EncounterSetting",
    "PetOwned",
    "PetSpecies",
    "HealthSample",
    "PetlandMap",
    "PetState",
    "RubyEvent",
    "RubyRule",
    "Question",
    "QuestionLabel",
    "QuestionOption",
    "QuestionSet",
    "QuestionSetLabel",
    "ScoreConversion",
    "ScoreScale",
    "TestCollection",
    "Topic",
    "User",
    "UserProfile",
    "VocabularyAudio",
    "VocabularyCollection",
    "VocabularyCollectionItem",
    "VocabularyEntry",
    "VocabularyReviewLog",
    "VocabularyReviewState",
    "VocabularyTopic",
    "VocabularyTopicSession",
]
