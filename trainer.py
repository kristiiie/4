"""
Персонализированный тренажёр для начальной школы.

Уровень выполнения: "хорошо".

Логика уровня "хорошо":
1. При первом запуске программа выбирает 10 случайных вопросов из базы.
2. После прохождения сохраняется файл user_answers.txt.
3. При следующем запуске программа берёт до 5 вопросов, на которые раньше
   был дан неправильный ответ, и добирает сессию случайными вопросами до 10.
4. Категория вопроса хранится в базе и в файле ответов, но для уровня
   "хорошо" не используется при подборе новых вопросов.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import random
import sys


QUESTIONS_FILE = Path("questions.txt")
ANSWERS_FILE = Path("user_answers.txt")

SESSION_SIZE = 10
REPEAT_MISTAKES_COUNT = 5
SEPARATOR = ";"


@dataclass
class Question:
    """Описывает один вопрос из базы."""

    question_id: int
    category: str
    subject: str
    text: str
    answer: str


@dataclass
class AnswerResult:
    """Хранит результат ответа пользователя на один вопрос."""

    question: Question
    user_answer: str
    is_correct: bool


class QuestionStorage:
    """Загружает вопросы из текстовой базы."""

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path

    def load_questions(self) -> list[Question]:
        """Читает вопросы из файла questions.txt."""

        if not self.file_path.exists():
            raise FileNotFoundError(
                f"Не найден файл базы вопросов: {self.file_path}"
            )

        questions: list[Question] = []

        with self.file_path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                line = line.strip()

                if not line or line.startswith("#"):
                    continue

                parts = line.split(SEPARATOR)

                if len(parts) != 5:
                    raise ValueError(
                        "Ошибка в базе вопросов. "
                        f"Строка {line_number} должна содержать 5 полей: "
                        "id;category;subject;question;answer"
                    )

                question_id_text, category, subject, text, answer = parts

                try:
                    question_id = int(question_id_text)
                except ValueError as exc:
                    raise ValueError(
                        f"В строке {line_number} некорректный номер вопроса."
                    ) from exc

                questions.append(
                    Question(
                        question_id=question_id,
                        category=category.strip(),
                        subject=subject.strip(),
                        text=text.strip(),
                        answer=answer.strip(),
                    )
                )

        if len(questions) < SESSION_SIZE:
            raise ValueError(
                "В базе должно быть не меньше 10 вопросов для одной сессии."
            )

        return questions


class AnswerStorage:
    """Работает с файлом результатов предыдущей сессии."""

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path

    def has_previous_session(self) -> bool:
        """Проверяет, был ли тренажёр запущен ранее."""

        return self.file_path.exists() and self.file_path.stat().st_size > 0

    def load_wrong_question_ids(self) -> list[int]:
        """
        Возвращает номера вопросов, на которые в прошлой сессии были ошибки.

        Формат строки:
        question_id;category;error_status

        error_status:
        0 - ответ был правильным;
        1 - ответ был ошибочным.
        """

        if not self.has_previous_session():
            return []

        wrong_question_ids: list[int] = []

        with self.file_path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                line = line.strip()

                if not line:
                    continue

                parts = line.split(SEPARATOR)

                if len(parts) != 3:
                    print(
                        "Предупреждение: строка файла ответов пропущена, "
                        f"так как имеет неверный формат: {line_number}"
                    )
                    continue

                question_id_text, _category, error_status = parts

                if error_status.strip() != "1":
                    continue

                try:
                    wrong_question_ids.append(int(question_id_text))
                except ValueError:
                    print(
                        "Предупреждение: строка файла ответов пропущена, "
                        f"так как номер вопроса некорректен: {line_number}"
                    )

        return wrong_question_ids

    def save_session_results(self, results: list[AnswerResult]) -> None:
        """Очищает файл ответов и записывает результаты текущей сессии."""

        with self.file_path.open("w", encoding="utf-8") as file:
            for result in results:
                error_status = "0" if result.is_correct else "1"

                file.write(
                    f"{result.question.question_id}{SEPARATOR}"
                    f"{result.question.category}{SEPARATOR}"
                    f"{error_status}\n"
                )


class SessionBuilder:
    """Формирует набор вопросов для прохождения."""

    def __init__(self, questions: list[Question]) -> None:
        self.questions = questions
        self.questions_by_id = {
            question.question_id: question for question in questions
        }

    def build_session(self, wrong_question_ids: list[int]) -> list[Question]:
        """
        Формирует сессию из 10 вопросов.

        Если ошибок раньше не было, выбираются 10 случайных вопросов.
        Если ошибки были, сначала выбирается до 5 ошибочных вопросов,
        затем список добирается случайными вопросами.
        """

        selected_questions: list[Question] = []

        valid_wrong_questions = [
            self.questions_by_id[question_id]
            for question_id in wrong_question_ids
            if question_id in self.questions_by_id
        ]

        if valid_wrong_questions:
            mistake_part_size = min(
                REPEAT_MISTAKES_COUNT,
                len(valid_wrong_questions),
            )
            selected_questions.extend(
                random.sample(valid_wrong_questions, mistake_part_size)
            )

        selected_ids = {
            question.question_id for question in selected_questions
        }

        available_random_questions = [
            question
            for question in self.questions
            if question.question_id not in selected_ids
        ]

        needed_random_count = SESSION_SIZE - len(selected_questions)

        if needed_random_count > 0:
            selected_questions.extend(
                random.sample(available_random_questions, needed_random_count)
            )

        random.shuffle(selected_questions)

        return selected_questions


class Trainer:
    """Проводит учебную сессию и выводит отчёт."""

    def __init__(self, questions: list[Question]) -> None:
        self.questions = questions

    def run(self) -> list[AnswerResult]:
        """Запускает прохождение сессии."""

        print("\nПерсонализированный тренажёр для начальной школы")
        print("=" * 55)
        print("Введите ответ и нажмите Enter.")
        print("Для выхода до завершения сессии введите команду: выход")
        print("=" * 55)

        results: list[AnswerResult] = []

        for index, question in enumerate(self.questions, start=1):
            print(f"\nВопрос {index} из {len(self.questions)}")
            print(f"Предмет: {question.subject}")
            print(f"Задание: {question.text}")

            user_answer = input("Ваш ответ: ").strip()

            if user_answer.lower() in {"выход", "exit", "quit"}:
                print("\nСессия прервана. Результаты пройденных вопросов сохранены.")
                break

            is_correct = self._check_answer(user_answer, question.answer)

            if is_correct:
                print("Верно!")
            else:
                print(f"Неверно. Правильный ответ: {question.answer}")

            results.append(
                AnswerResult(
                    question=question,
                    user_answer=user_answer,
                    is_correct=is_correct,
                )
            )

        self._print_report(results)

        return results

    @staticmethod
    def _normalize_answer(answer: str) -> str:
        """
        Приводит ответ к единому виду.

        Учитываются частые различия:
        - лишние пробелы;
        - буквы Ё/Е;
        - запятая вместо точки в числах;
        - разный регистр букв.
        """

        normalized = answer.strip().lower()
        normalized = normalized.replace("ё", "е")
        normalized = normalized.replace(",", ".")
        normalized = " ".join(normalized.split())

        return normalized

    def _check_answer(self, user_answer: str, correct_answer: str) -> bool:
        """
        Проверяет ответ.

        В базе можно указать несколько допустимых вариантов через символ |.
        Например: Москва|город Москва
        """

        normalized_user_answer = self._normalize_answer(user_answer)

        correct_variants = [
            self._normalize_answer(variant)
            for variant in correct_answer.split("|")
        ]

        return normalized_user_answer in correct_variants

    @staticmethod
    def _print_report(results: list[AnswerResult]) -> None:
        """Печатает итоговый отчёт по сессии."""

        print("\nОтчёт о прохождении")
        print("=" * 55)

        if not results:
            print("Нет отвеченных вопросов.")
            return

        correct_count = sum(1 for result in results if result.is_correct)
        total_count = len(results)
        percent = correct_count / total_count * 100

        print(f"Всего отвечено: {total_count}")
        print(f"Правильных ответов: {correct_count}")
        print(f"Ошибок: {total_count - correct_count}")
        print(f"Результат: {percent:.1f}%")

        print("\nПодробности:")
        for index, result in enumerate(results, start=1):
            status = "верно" if result.is_correct else "ошибка"
            print(
                f"{index}. Вопрос №{result.question.question_id}: "
                f"{status}; ваш ответ: {result.user_answer or 'пустой ответ'}"
            )


def main() -> int:
    """Точка входа в программу."""

    try:
        question_storage = QuestionStorage(QUESTIONS_FILE)
        questions = question_storage.load_questions()

        answer_storage = AnswerStorage(ANSWERS_FILE)

        if answer_storage.has_previous_session():
            print("Найден файл результатов предыдущей сессии.")
            wrong_question_ids = answer_storage.load_wrong_question_ids()
        else:
            print("Предыдущая сессия не найдена. Будет создана случайная сессия.")
            wrong_question_ids = []

        session_builder = SessionBuilder(questions)
        session_questions = session_builder.build_session(wrong_question_ids)

        trainer = Trainer(session_questions)
        results = trainer.run()

        answer_storage.save_session_results(results)

        print(f"\nРезультаты сохранены в файл: {ANSWERS_FILE}")

    except (FileNotFoundError, ValueError) as error:
        print(f"\nОшибка: {error}")
        return 1
    except KeyboardInterrupt:
        print("\n\nРабота программы остановлена пользователем.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
