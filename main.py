import os
import sys
import re

from docs_processing import (
    controls_chunking, extract_controls_from_pdf,
    extract_from_pdf, docs_chunking,
)
from database import (
    chroma_db_init,
    insert_into_collection_safe,
    clear_collection,
    db_query,
    db_get_by_control_ids,
)
import interaction_with_llm as llm

CONTROLS_PDF = "Docs/НД ТЗІ 3.6-006-24.pdf"
DOCS_FOLDER  = "Docs"


def _index_single_doc(collection, file_path):
    text = extract_from_pdf(file_path)
    documents, ids, metadatas = docs_chunking(text)
    insert_into_collection_safe(collection, documents, ids, metadatas)


def _index_controls(collection):
    text = extract_controls_from_pdf(CONTROLS_PDF)
    documents, ids, metadatas = controls_chunking(text)
    insert_into_collection_safe(collection, documents, ids, metadatas)


def _index_all(collection):
    for filename in os.listdir(DOCS_FOLDER):
        _index_single_doc(collection, os.path.join(DOCS_FOLDER, filename))
    _index_controls(collection)


def initialize_database(collection):
    if collection.count() == 0:
        print("База порожня. Індексую документи...")
        _index_all(collection)
        print(f"База готова ({collection.count()} записів).")
    else:
        print(f"База готова ({collection.count()} записів).")


def update_database(collection):
    print("Очищую базу та переіндексовую документи...")
    clear_collection(collection)
    _index_all(collection)
    print(f"База оновлена ({collection.count()} записів).")


def extract_control_ids(text):
    found = re.findall(r"[A-ZА-ЯІЇЄ]{2}-\d+", text.upper())
    return list(set(found))


def _choose_output_format():
    print("\nФормат збереження:")
    print("  1 - Тільки Markdown (.md)")
    print("  2 - Markdown + DOCX (.docx)")
    return input("Ваш вибір [2]: ").strip() or "2"


def _save_outputs(profile_content, base_name, fmt_choice):
    md_path = f"{base_name}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(profile_content)
    print(f"Markdown збережено: {md_path}")

    if fmt_choice == "2":
        print(f"DOCX збережено: {llm.save_profile_as_docx(profile_content, base_name)}")


def mode_generate_profile(collection):
    baseline_file_id = None
    selected_profile = None

    profiles = llm.list_baseline_profiles()
    has_profiles_folder = os.path.exists(llm.BASELINE_PROFILES_FOLDER) and bool(
        [f for f in os.listdir(llm.BASELINE_PROFILES_FOLDER) if f.lower().endswith(".pdf")]
    )

    if has_profiles_folder:
        print("\nЗнайдено папку базових профілів.")
        print("  1 - Обрати автоматично")
        print("  2 - Обрати вручну")
        print("  3 - Не використовувати")
        profile_choice = input("Ваш вибір [1]: ").strip() or "1"

        if profile_choice in ("1", "2"):
            profiles = llm.upload_baseline_profiles()

        if profile_choice == "1" and profiles:
            print("Обираю профіль автоматично...")
            selected_profile, baseline_file_id = llm.select_baseline_profile_auto(
                profiles, llm.read_system_specs()
            )
            print(f"Обрано: {selected_profile}")

        elif profile_choice == "2" and profiles:
            names = list(profiles.keys())
            for i, name in enumerate(names, 1):
                print(f"  {i}. {name}")
            try:
                idx = int(input("Введіть номер профілю: ").strip()) - 1
                if 0 <= idx < len(names):
                    selected_profile = names[idx]
                    baseline_file_id = profiles[selected_profile]["file_id"]
                    print(f"Обрано: {selected_profile}")
                else:
                    print("Невірний номер — профіль не буде використано.")
            except ValueError:
                print("Невірний ввід — профіль не буде використано.")

    question = input("\nДодаткові вказівки (або Enter для стандартного): ").strip()
    if not question:
        question = "Згенеруй цільовий профіль безпеки на основі базового."

    retrieved_docs = db_query(
        collection,
        "Базовий набір контролів безпеки політики",
        n_results=20,
        where_filter={"document_type": "security_control"},
    )
    context = "\n".join(retrieved_docs)

    label = f" (на основі '{selected_profile}')" if selected_profile else ""
    print(f"\nГенерую цільовий профіль безпеки{label}...\n")
    print("─" * 72)
    profile_content = llm.llm_query_profile(context, question, baseline_file_id)
    print("─" * 72)

    _save_outputs(profile_content, "Target_Security_Profile", _choose_output_format())
    print("\nГотово!")


def main():
    print("=== AI Security Advisor ===")
    collection = chroma_db_init()
    initialize_database(collection)

    while True:
        print("\n1 - Запитання (Q&A)")
        print("2 - Рекомендації щодо контролю безпеки")
        print("3 - Генерація цільового профілю безпеки")
        print("4 - Оновити базу даних")
        print("0 - Вихід")

        choice = input("\nВибір: ").strip()

        if choice == "0":
            sys.exit(0)

        elif choice == "1":
            question = input("\nЗапитання: ")
            context = "\n".join(db_query(collection, question, n_results=5))
            print(f"\n{llm.llm_query_qa(context, question)}")

        elif choice == "2":
            question = input("\nЯкі контролі вас цікавлять? ")
            control_ids = extract_control_ids(question)

            if control_ids:
                retrieved_docs = db_get_by_control_ids(collection, control_ids)
                if not retrieved_docs:
                    retrieved_docs = db_query(
                        collection, question, n_results=5,
                        where_filter={"document_type": "security_control"},
                    )
            else:
                retrieved_docs = db_query(
                    collection, question, n_results=5,
                    where_filter={"document_type": "security_control"},
                )

            print(f"\n{llm.llm_query_recommendations(chr(10).join(retrieved_docs), question)}")

        elif choice == "3":
            mode_generate_profile(collection)

        elif choice == "4":
            update_database(collection)

        else:
            print("Невірний вибір.")


if __name__ == "__main__":
    main()