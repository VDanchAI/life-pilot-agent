"""Bot FSM states."""

from aiogram.fsm.state import State, StatesGroup


class DoCommandState(StatesGroup):
    """States for /do command flow."""

    waiting_for_input = State()  # Waiting for voice or text after /do


class ProcessStates(StatesGroup):
    """States for /process command flow."""

    waiting_clarification = State()  # Clarify uncertain items (ТЗ 2)
    waiting_correction = State()     # Correction input after report (ТЗ 1.2)


class MonthlyStates(StatesGroup):
    """States for monthly report flow."""

    waiting_reformulation = State()  # Waiting for new task wording (ТЗ 3)


class ReflectionStates(StatesGroup):
    """States for reflection questions flow."""

    waiting_response = State()  # Waiting for reflection answer (ТЗ 4)


class GrowStates(StatesGroup):
    """States for GROW coaching session flow."""

    answering = State()     # Text + voice, multi-message answer collection
    confirming = State()    # Confirm or correct Claude summary
    correcting = State()    # User provides correction instructions


class RecallStates(StatesGroup):
    """States for /recall command flow."""

    waiting_query = State()  # Waiting for search query (ТЗ 5)


class CoachStates(StatesGroup):
    """States for Coach Mode conversational flow."""

    chatting = State()    # Active coaching dialogue
    saving = State()      # Waiting for confirm/skip after "стоп"
