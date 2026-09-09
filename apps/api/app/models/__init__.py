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
from app.models.feedback import (
    FEEDBACK_STATUSES,
    FEEDBACK_TYPES,
    PENDING_CAP,
    Feedback,
)
from app.models.grammar import (
    GrammarAttempt,
    GrammarLesson,
    GrammarLessonCompletion,
    GrammarLessonQuestion,
    GrammarTopic,
)
from app.models.health import HealthSample
from app.models.identity import IDENTITY_PROVIDERS, UserIdentity
from app.models.image import ImageAsset
from app.models.knowledge import KnowledgeChunk
from app.models.labels import QuestionLabel, QuestionSetLabel
from app.models.part_practice import PartSession, PartSessionItem, PartTactics
from app.models.pet import (
    Creature,
    EggSetting,
    PetlandMap,
    PetOwned,
    PetSpecies,
    PetState,
)
from app.models.placement import PlacementResult
from app.models.planner_eval import PlannerEval
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
from app.models.study_plan import StudyPlan, StudyPlanItem
from app.models.topic import Topic
from app.models.user import User
from app.models.vocabulary import (
    CollocationDetail,
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
    "COLLOCATION_PATTERNS",
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
    "GrammarAttempt",
    "GrammarLesson",
    "GrammarLessonCompletion",
    "GrammarLessonQuestion",
    "GrammarTopic",
    "ImageAsset",
    "KnowledgeChunk",
    "PartSession",
    "PlacementResult",
    "PlannerEval",
    "StudyPlan",
    "StudyPlanItem",
    "PartSessionItem",
    "PartTactics",
    "PracticeTest",
    "PracticeTestQuestion",
    "EggSetting",
    "Encounter",
    "EncounterSetting",
    "PetOwned",
    "PetSpecies",
    "FEEDBACK_STATUSES",
    "FEEDBACK_TYPES",
    "Feedback",
    "HealthSample",
    "PENDING_CAP",
    "Creature",
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
    "CollocationDetail",
]
