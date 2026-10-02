import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from repositories.database import get_session, CourseDB, SubjectContextDB, AppSettingDB
from repositories.subject_repo import SubjectRepository

def main():
    repo = SubjectRepository()
    subjects = repo.list_subjects()
    print(f"Found {len(subjects)} subjects in database.")
    
    for s in subjects:
        sid = s["subject_id"]
        cname = s["course_name"]
        print(f"Deleting subject: {cname} ({sid})")
        repo.delete_subject(sid)
        
    with get_session() as session:
        count_ctx = session.query(SubjectContextDB).delete()
        count_cfg = session.query(AppSettingDB).filter(AppSettingDB.key == "active_subject_id").delete()
        session.commit()
        print(f"Cleared {count_ctx} context record(s) and reset active_subject_id.")
        
    remaining = repo.list_subjects()
    print(f"Deletion complete. Remaining subjects count: {len(remaining)}")

if __name__ == "__main__":
    main()
