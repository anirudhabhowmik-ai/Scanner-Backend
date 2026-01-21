# tasks.py
import threading
import ocrmypdf

# Dictionary to store task status
tasks = {}

def ocr_task(task_id, input_path, output_path, languages):
    """Background OCR task"""
    try:
        tasks[task_id] = {"status": "processing"}
        ocrmypdf.ocr(
            input_path,
            output_path,
            language=languages,
            force_ocr=True,
            deskew=True,
            rotate_pages=True,
            optimize=None,
            pdfa=False
        )
        tasks[task_id] = {"status": "done", "output": output_path}
    except Exception as e:
        tasks[task_id] = {"status": "error", "error": str(e)}
