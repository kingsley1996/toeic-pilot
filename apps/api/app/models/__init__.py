from app.models.ai import AI_INTERACTION_STATUSES, AiInteraction
from app.models.ai_config import AiFeatureConfig
from app.models.audio import AudioAsset
from app.models.dictation import (
    DictationAttempt,
    DictationItem,
    DictationSection,
    DictationStory,
    DictationTopic,
)
from app.models.image import ImageAsset
from app.models.labels import QuestionLabel, QuestionSetLabel
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
from app.models.scoring import ScoreConversion, ScoreScale
from app.models.topic import Topic
from app.models.user import User
from app.models.vocabulary import (
    VocabularyAudio,
    VocabularyEntry,
    VocabularyReviewLog,
    VocabularyReviewState,
    VocabularyTopic,
)

# Every model must be reachable from here: this is the single import that
# registers the tables on Base.metadata for app.main, alembic/env.py and the test
# fixture alike. A model missing from this list produces "no such table" in tests
# and an empty autogenerate diff in Alembic.
__all__ = [
    "AI_INTERACTION_STATUSES",
    "AiFeatureConfig",
    "AiInteraction",
    "Attempt",
    "AttemptItem",
    "AttemptPart",
    "AudioAsset",
    "DictationAttempt",
    "DictationItem",
    "DictationSection",
    "DictationStory",
    "DictationTopic",
    "ImageAsset",
    "PracticeTest",
    "PracticeTestQuestion",
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
    "VocabularyEntry",
    "VocabularyReviewLog",
    "VocabularyReviewState",
    "VocabularyTopic",
]
