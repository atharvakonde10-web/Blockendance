# Python module imports
import datetime as dt
import re
from flask import Flask, request, render_template, jsonify, redirect

# Importing local functions
from genesis import create_blockchain
from newBlock import add_block
from getBlock import find_records, get_all_attendance_records, get_block_by_index
from checkChain import check_integrity, get_blockchain_stats
from persistence import save_blockchain, load_blockchain, export_blockchain_csv
from analytics import get_attendance_analytics, generate_attendance_report, export_analytics

# Flask declarations
app = Flask(__name__)
app.config['SECRET_KEY'] = 'blockendance-secret-key-2018'

# Add cache control headers
@app.after_request
def after_request(response):
    response.headers.add(
        'Cache-Control',
        'no-store, no-cache, must-revalidate, post-check=0, pre-check=0'
    )
    return response

# Initializing blockchain with the genesis block
# Try to load existing blockchain first
loaded_blockchain, load_message = load_blockchain()
if loaded_blockchain:
    blockchain = loaded_blockchain
    print(f"Loaded existing blockchain: {load_message}")
else:
    blockchain = create_blockchain()
    print(f"Created new blockchain: {load_message}")
    # Save the new blockchain
    save_blockchain(blockchain)

print(f"Blockchain initialized with genesis block: {blockchain[0]}")

# Default Landing page of the app
@app.route('/', methods=['GET'])
def index():
    return render_template("index.html")


# Get Form input and decide what is to be done with it
@app.route('/', methods=['POST'])
def parse_request():
    try:
        # Step 3: Teacher submits attendance from attendance.html
        if "roll_no1" in request.form:
            # Extract form data
            form_data = [
                request.form.get("teacher_name", "").strip(),
                request.form.get("date", "").strip(),
                request.form.get("course", "").strip(),
                request.form.get("year", "").strip(),
                request.form.get("engg_year", "").strip()
            ]

            # Validate required data
            if not all(form_data[:4]):
                return render_template(
                    "result.html",
                    result="Error: Missing required information"
                )

            result = add_block(request.form, form_data, blockchain)

            # Auto-save blockchain after adding new block
            if "added" in result:
                save_success, save_msg = save_blockchain(blockchain)
                if save_success:
                    result += f" Blockchain automatically saved."
                else:
                    result += f" Warning: Failed to save blockchain - {save_msg}"

            stats = get_blockchain_stats(blockchain)
            return render_template("result.html", result=result, stats=stats)

        # Step 1: Teacher enters name from index.html
        elif request.form.get("name"):
            teacher_name = request.form.get("name").strip()
            if not teacher_name:
                return render_template("index.html", error="Please enter a valid name")

            return render_template(
                "class.html",
                name=teacher_name,
                date=dt.date.today()
            )

        # Step 2: Teacher enters class details from class.html
        elif request.form.get("number"):
            teacher_name = request.form.get("teacher_name", "").strip()
            course = request.form.get("course", "").strip()
            year = request.form.get("year", "").strip()
            engg_year = request.form.get("engg_year", "").strip()
            number = request.form.get("number", "0")

            # Validate inputs
            if not all([teacher_name, course, year, engg_year]):
                return render_template(
                    "class.html",
                    error="Please fill all required fields",
                    name=teacher_name,
                    date=dt.date.today(),
                    engg_year=engg_year
                )

            try:
                student_count = int(number)
                if student_count <= 0:
                    raise ValueError("Invalid student count")
            except ValueError:
                return render_template(
                    "class.html",
                    error="Please enter a valid number of students",
                    name=teacher_name,
                    date=dt.date.today(),
                    engg_year=engg_year
                )

            return render_template(
                "attendance.html",
                name=teacher_name,
                course=course,
                year=year,
                engg_year=engg_year,
                number=student_count,
                date=str(dt.date.today())
            )

        else:
            return render_template("index.html", error="Invalid form submission")

    except Exception as e:
        return render_template("index.html", error=f"An error occurred: {str(e)}")


# Show page to get information for fetching records
@app.route('/view.html', methods=['GET'])
def view():
    return render_template("class.html", view_mode=True)


# Process form input for fetching records from the blockchain
@app.route('/view.html', methods=['POST'])
def show_records():
    try:
        name = request.form.get("name", "").strip()
        course = request.form.get("course", "").strip()
        year = request.form.get("year", "").strip()
        engg_year = request.form.get("engg_year", "").strip()
        date = request.form.get("date", "").strip()
        number = request.form.get("number", "0")

        if not all([name, course, year, engg_year, date]):
            return render_template(
                "class.html",
                view_mode=True,
                engg_year=engg_year,
                error="Please fill all required fields"
            )

        # Parse total students (optional — used for absent display, NOT for search matching)
        try:
            total_students = int(number)
            if total_students < 0:
                total_students = 0
        except (ValueError, TypeError):
            total_students = 0

        def clean_str(s):
            return str(s).strip().lower() if s is not None else ""

        name_c = clean_str(name)
        course_c = clean_str(course)
        year_c = clean_str(year)
        engg_year_c = clean_str(engg_year)
        date_c = clean_str(date)

        # Flexible search: match newest block first, case-insensitive
        matched_block = None
        display_number = 30
        for b in reversed(blockchain):
            if (b.index > 0 and
                    isinstance(b.data, dict) and
                    b.data.get("type") == "attendance"):
                b_name = clean_str(b.data.get("teacher_name"))
                b_date = clean_str(b.data.get("date"))
                b_course = clean_str(b.data.get("course"))
                b_year = clean_str(b.data.get("year"))
                b_engg_year = clean_str(b.data.get("engg_year"))

                # Check engg_year match: if block has engg_year, must match
                engg_match = True
                if engg_year_c and b_engg_year:
                    engg_match = (b_engg_year == engg_year_c)

                # Check match on date, course, year, teacher name, and engg_year
                if (b_date == date_c and
                        b_course == course_c and
                        b_year == year_c and
                        engg_match and
                        (b_name == name_c or name_c in b_name or b_name in name_c)):
                    # Get block's actual total students count
                    b_total = b.data.get("total_students", 0)
                    if not b_total or b_total <= 0:
                        max_r = len(b.data.get("present_students", []))
                        for ps in b.data.get("present_students", []):
                            try:
                                num_val = int(str(ps).split("-")[-1])
                                if num_val > max_r:
                                    max_r = num_val
                            except (ValueError, TypeError):
                                pass
                        b_total = max_r if max_r > 0 else 30

                    # If user specified a total student count, it MUST match this block's count!
                    if total_students > 0 and b_total != total_students:
                        continue

                    matched_block = b
                    display_number = b_total
                    break

        if matched_block is None:
            return render_template(
                "view.html",
                name=name,
                course=course,
                year=year,
                engg_year=engg_year,
                date=date,
                number=total_students,
                status=[],
                present_roll_indices=[],
                error="No records found for the specified criteria"
            )

        present_students = matched_block.data.get("present_students", [])
        matched_engg_year = matched_block.data.get("engg_year", engg_year)

        # Build list of present roll identifiers for exact table matching
        present_roll_indices = []
        for ps in present_students:
            ps_s = str(ps).strip()
            present_roll_indices.append(ps_s)
            parts = ps_s.split('-')
            if parts:
                present_roll_indices.append(parts[-1].strip())
                try:
                    present_roll_indices.append(str(int(parts[-1])))
                    present_roll_indices.append(f"{int(parts[-1]):02d}")
                except ValueError:
                    pass

        return render_template(
            "view.html",
            name=matched_block.data.get("teacher_name", name),
            course=matched_block.data.get("course", course),
            year=matched_block.data.get("year", year),
            engg_year=matched_engg_year,
            date=matched_block.data.get("date", date),
            number=display_number,
            status=present_students,
            present_roll_indices=present_roll_indices,
            block_index=matched_block.index,
            success=f"Found attendance record — {len(present_students)} students present (Block #{matched_block.index})"
        )

    except Exception as e:
        return render_template(
            "class.html",
            view_mode=True,
            error=f"An error occurred: {str(e)}"
        )


# View specific block by index
@app.route('/view/<int:block_index>', methods=['GET'])
def view_block(block_index):
    try:
        block = get_block_by_index(blockchain, block_index)
        if not block or block.index == 0 or not isinstance(block.data, dict) or block.data.get("type") != "attendance":
            return render_template("class.html", view_mode=True, error=f"Block #{block_index} not found or is not an attendance record")
        
        block_content = block.data
        present_students = block_content.get("present_students", [])
        block_total = block_content.get("total_students", 0)
        block_engg_year = block_content.get("engg_year", "")

        if block_total and block_total > 0:
            display_number = block_total
        else:
            max_r = len(present_students)
            for ps in present_students:
                try:
                    num_val = int(str(ps).split("-")[-1])
                    if num_val > max_r:
                        max_r = num_val
                except (ValueError, TypeError):
                    pass
            display_number = max_r if max_r > 0 else 30

        present_roll_indices = []
        for ps in present_students:
            ps_s = str(ps).strip()
            present_roll_indices.append(ps_s)
            parts = ps_s.split('-')
            if parts:
                present_roll_indices.append(parts[-1].strip())
                try:
                    present_roll_indices.append(str(int(parts[-1])))
                    present_roll_indices.append(f"{int(parts[-1]):02d}")
                except ValueError:
                    pass

        return render_template(
            "view.html",
            name=block_content.get("teacher_name", ""),
            course=block_content.get("course", ""),
            year=block_content.get("year", ""),
            engg_year=block_engg_year,
            date=block_content.get("date", ""),
            number=display_number,
            status=present_students,
            present_roll_indices=present_roll_indices,
            block_index=block.index,
            success=f"Viewing attendance record for Block #{block.index}"
        )
    except Exception as e:
        return render_template("class.html", view_mode=True, error=str(e))


# Edit/Modify specific block to demonstrate blockchain tampering
@app.route('/edit/<int:block_index>', methods=['GET', 'POST'])
def edit_record(block_index):
    try:
        block = get_block_by_index(blockchain, block_index)
        if not block or block.index == 0 or not isinstance(block.data, dict) or block.data.get("type") != "attendance":
            return render_template("class.html", view_mode=True, error=f"Block #{block_index} not found or is not an attendance record")

        if request.method == 'GET':
            present_students = block.data.get("present_students", [])
            present_students_text = ", ".join(present_students)
            total_students = block.data.get("total_students", 0)
            if not total_students:
                max_r = 0
                for ps in present_students:
                    try:
                        num_val = int(str(ps).split("-")[-1])
                        if num_val > max_r:
                            max_r = num_val
                    except (ValueError, TypeError):
                        pass
                total_students = max_r if max_r > 0 else 30

            return render_template(
                "edit.html",
                block_index=block.index,
                data=block.data,
                total_students=total_students,
                present_students_text=present_students_text,
                block_hash=block.hash,
                prev_hash=block.prev_hash
            )

        # POST: Modify attendance data WITHOUT recalculating hash!
        teacher_name = request.form.get("teacher_name", "").strip()
        date = request.form.get("date", "").strip()
        course = request.form.get("course", "").strip()
        year = request.form.get("year", "").strip()
        engg_year = request.form.get("engg_year", "").strip()
        present_students_raw = request.form.get("present_students", "").strip()

        if not all([teacher_name, date, course, year, present_students_raw]):
            return render_template(
                "edit.html",
                block_index=block.index,
                data=block.data,
                total_students=block.data.get("total_students", 30),
                present_students_text=present_students_raw,
                block_hash=block.hash,
                prev_hash=block.prev_hash,
                error="Please fill all required fields"
            )

        tokens = [s.strip() for s in re.split(r'[\r\n,]+', present_students_raw) if s.strip()]
        if not tokens:
            return render_template(
                "edit.html",
                block_index=block.index,
                data=block.data,
                total_students=block.data.get("total_students", 30),
                present_students_text=present_students_raw,
                block_hash=block.hash,
                prev_hash=block.prev_hash,
                error="Please provide at least one student roll number"
            )

        # Modify the data directly, PRESERVING original stored block.hash
        orig_total = block.data.get("total_students")
        block.data = {
            "type": "attendance",
            "teacher_name": teacher_name,
            "date": date,
            "course": course,
            "year": year,
            "engg_year": engg_year,
            "total_students": orig_total if orig_total else len(tokens),
            "present_students": tokens
        }

        # Save modified blockchain to disk (persistence preserves stored hash)
        save_blockchain(blockchain)

        # Check integrity to show failure
        integrity_result = check_integrity(blockchain)
        stats = get_blockchain_stats(blockchain)

        return render_template(
            "result.html",
            result=f"Block #{block.index} attendance was modified! Integrity Check: {integrity_result}",
            stats=stats
        )

    except Exception as e:
        return render_template("class.html", view_mode=True, error=f"Error modifying block: {str(e)}")


# Show page with result of checking blockchain integrity
@app.route('/result.html', methods=['GET'])
def check():
    try:
        integrity_result = check_integrity(blockchain)
        stats = get_blockchain_stats(blockchain)
        return render_template(
            "result.html",
            result=integrity_result,
            stats=stats
        )
    except Exception as e:
        return render_template(
            "result.html",
            result=f"Error checking blockchain: {str(e)}"
        )


# API endpoint to get blockchain statistics
@app.route('/api/stats', methods=['GET'])
def api_stats():
    try:
        stats = get_blockchain_stats(blockchain)
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# API endpoint to get all attendance records
@app.route('/api/records', methods=['GET'])
def api_records():
    try:
        records = get_all_attendance_records(blockchain)
        return jsonify({"records": records, "count": len(records)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# API endpoint to get analytics
@app.route('/api/analytics', methods=['GET'])
def api_analytics():
    try:
        analytics = get_attendance_analytics(blockchain)
        return jsonify(analytics)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# API endpoint to export data
@app.route('/api/export/<format>', methods=['GET'])
def api_export(format):
    try:
        if format == 'csv':
            success, message = export_blockchain_csv(blockchain)
            return jsonify({"success": success, "message": message})
        elif format == 'analytics':
            success, message = export_analytics(blockchain)
            return jsonify({"success": success, "message": message})
        elif format == 'json':
            success, message = save_blockchain(blockchain)
            return jsonify({"success": success, "message": message})
        else:
            return jsonify({"error": "Invalid export format"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# API endpoint to get attendance report
@app.route('/api/report', methods=['GET'])
def api_report():
    try:
        format_type = request.args.get('format', 'json')
        if format_type == 'text':
            report = generate_attendance_report(blockchain, format='text')
            return report, 200, {'Content-Type': 'text/plain'}
        else:
            report = generate_attendance_report(blockchain, format='json')
            return report, 200, {'Content-Type': 'application/json'}
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# API endpoint to load blockchain from file
@app.route('/api/load', methods=['POST'])
def api_load():
    try:
        global blockchain
        loaded_blockchain, message = load_blockchain()
        if loaded_blockchain:
            blockchain = loaded_blockchain
            return jsonify({
                "success": True,
                "message": message,
                "blocks": len(blockchain)
            })
        else:
            return jsonify({"success": False, "message": message}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# NEW: Transactions page
@app.route('/transactions', methods=['GET'])
def transactions():
    try:
        chain_data = []
        for i, block in enumerate(blockchain):
            is_hash_valid = block.is_valid()
            is_linked = (i == 0) or (block.prev_hash == blockchain[i - 1].hash)
            block_info = {
                "index": block.index,
                "timestamp": block.timestamp,
                "hash": block.hash,
                "prev_hash": "0" if i == 0 else block.prev_hash,
                "data": block.data,
                "is_valid": is_hash_valid,
                "is_tampered": not is_hash_valid or not is_linked
            }
            chain_data.append(block_info)

        return render_template("transactions.html", chain=chain_data)

    except Exception as e:
        return render_template("transactions.html", chain=[], error=str(e))


@app.route('/reset', methods=['POST'])
def reset_blockchain():
    try:
        global blockchain
        # Keep only the genesis block
        genesis_block = blockchain[0]
        blockchain = [genesis_block]

        # Save the reset blockchain
        save_success, save_msg = save_blockchain(blockchain)

        if save_success:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
                return jsonify({"success": True, "message": "Blockchain reset successfully. Only genesis block kept."})
            return redirect('/transactions')
        else:
            return jsonify({"success": False, "message": f"Blockchain reset but failed to save: {save_msg}"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# Start the flask app when program is executed
if __name__ == "__main__":
    print("Starting Blockendance - Blockchain-based Attendance System")
    print(f"Blockchain initialized with {len(blockchain)} blocks")
    print("Access the application at: http://localhost:5001")
    app.run(debug=True, host='0.0.0.0', port=5001)
