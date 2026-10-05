import pytest

from tasks import services
from tasks.models import Task
from tests.factories import ProjectFactory, TaskFactory

pytestmark = pytest.mark.django_db

TODO, DOING, DONE = Task.Status.TODO, Task.Status.IN_PROGRESS, Task.Status.DONE


def column(project, status):
    """Titles in a column, top to bottom."""
    return list(
        Task.objects.filter(project=project, status=status)
        .order_by("position")
        .values_list("title", flat=True)
    )


def positions(project, status):
    return list(
        Task.objects.filter(project=project, status=status)
        .order_by("position")
        .values_list("position", flat=True)
    )


@pytest.fixture
def board():
    """A project with A, B, C in To Do and X, Y in In Progress."""
    project = ProjectFactory()
    tasks = {t: TaskFactory(project=project, title=t) for t in "ABC"}
    tasks |= {t: TaskFactory(project=project, title=t, status=DOING) for t in "XY"}
    return project, tasks


class TestCreate:
    def test_new_tasks_go_to_the_bottom_of_their_column(self):
        project = ProjectFactory()
        first = services.create_task(project=project, created_by=project.owner, title="1")
        second = services.create_task(project=project, created_by=project.owner, title="2")
        done = services.create_task(
            project=project, created_by=project.owner, title="3", status=DONE
        )
        assert (first.position, second.position, done.position) == (0, 1, 0)
        assert first.created_by == project.owner


class TestMove:
    def test_reorder_within_a_column(self, board):
        project, tasks = board
        changed_column = services.move_task(
            tasks["C"], status=TODO, position=0, actor=project.owner
        )
        assert column(project, TODO) == ["C", "A", "B"]
        assert positions(project, TODO) == [0, 1, 2]
        assert changed_column is False

    def test_move_down_within_a_column(self, board):
        project, tasks = board
        services.move_task(tasks["A"], status=TODO, position=2, actor=project.owner)
        assert column(project, TODO) == ["B", "C", "A"]

    def test_move_to_another_column_at_a_position(self, board):
        project, tasks = board
        changed_column = services.move_task(
            tasks["B"], status=DOING, position=1, actor=project.owner
        )

        assert column(project, DOING) == ["X", "B", "Y"]
        assert positions(project, DOING) == [0, 1, 2]
        # The column it left has no gap.
        assert column(project, TODO) == ["A", "C"]
        assert positions(project, TODO) == [0, 1]
        assert changed_column is True
        tasks["B"].refresh_from_db()
        assert tasks["B"].status == DOING

    def test_move_into_an_empty_column(self, board):
        project, tasks = board
        services.move_task(tasks["A"], status=DONE, position=0, actor=project.owner)
        assert column(project, DONE) == ["A"]

    def test_position_past_the_end_is_clamped_to_the_bottom(self, board):
        project, tasks = board
        services.move_task(tasks["A"], status=DOING, position=99, actor=project.owner)
        assert column(project, DOING) == ["X", "Y", "A"]
        assert positions(project, DOING) == [0, 1, 2]

    def test_unknown_status_is_rejected(self, board):
        project, tasks = board
        with pytest.raises(ValueError):
            services.move_task(tasks["A"], status="archived", position=0, actor=project.owner)

    def test_moving_updates_updated_at(self, board):
        project, tasks = board
        before = tasks["A"].updated_at
        services.move_task(tasks["A"], status=DONE, position=0, actor=project.owner)
        tasks["A"].refresh_from_db()
        assert tasks["A"].updated_at > before

    def test_other_projects_are_untouched(self, board):
        project, tasks = board
        other = TaskFactory(title="Other")
        services.move_task(tasks["A"], status=TODO, position=2, actor=project.owner)
        other.refresh_from_db()
        assert other.position == 0


class TestUpdateAndDelete:
    def test_changing_status_in_the_form_moves_to_bottom_of_new_column(self, board):
        project, tasks = board
        task = tasks["A"]
        task.status = DOING  # what a bound ModelForm does before the service runs
        services.update_task(task, actor=project.owner, status=DOING, title="A2")

        assert column(project, DOING) == ["X", "Y", "A2"]
        assert column(project, TODO) == ["B", "C"]
        assert positions(project, TODO) == [0, 1]

    def test_editing_without_status_change_keeps_position(self, board):
        project, tasks = board
        services.update_task(tasks["B"], actor=project.owner, title="B2", status=TODO)
        assert column(project, TODO) == ["A", "B2", "C"]

    def test_delete_closes_the_gap(self, board):
        project, tasks = board
        services.delete_task(tasks["A"], actor=project.owner)
        assert column(project, TODO) == ["B", "C"]
        assert positions(project, TODO) == [0, 1]
