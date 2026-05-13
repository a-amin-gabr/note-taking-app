"""
DynamoDB Data Access Layer for Note-Taking App (Serverless)

Single-table design:
  PK                    SK              Entity
  USER#<user_id>        PROFILE         User profile
  USER#<user_id>        CAT#<cat_id>    Category
  USER#<user_id>        NOTE#<note_id>  Note
  NOTE#<note_id>        ATT#<att_id>    Attachment
  SHARE#<token>         META            Shared note pointer
"""
import os
import uuid
import secrets as _secrets
from datetime import datetime, timezone
from decimal import Decimal

TABLE_NAME = os.getenv("DYNAMODB_TABLE", "NotesApp")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Use mock DynamoDB for local dev (set USE_FAKE_DDB=1 env var)
USE_FAKE_DDB = os.getenv('USE_FAKE_DDB', '1') == '1'

if USE_FAKE_DDB:
    # =========================================================================
    # MOCK IN-MEMORY DYNAMODB
    # =========================================================================
    _store = {
        'users': {},        # user_id -> dict
        'categories': {},   # (user_id, cat_id) -> dict
        'notes': {},        # note_id -> dict
        'user_notes': {},   # user_id -> set(note_id)
        'attachments': {},  # (note_id, att_id) -> dict
        'shares': {},       # token -> (user_id, note_id)
    }

    def _now():
        return datetime.now(timezone.utc).isoformat()

    def _new_id():
        return uuid.uuid4().hex[:12]

    # Users
    def get_user(user_id):
        return _store['users'].get(user_id)

    def get_user_by_cognito_sub(cognito_sub):
        for u in _store['users'].values():
            if u.get('cognito_sub') == cognito_sub:
                return u
        return None

    def create_user(*, cognito_sub=None, email="", display_name="User", is_guest=False):
        user_id = cognito_sub if cognito_sub else f"guest_{_new_id()}"
        now = _now()
        item = {
            "user_id": user_id,
            "cognito_sub": cognito_sub or "",
            "email": email,
            "display_name": display_name,
            "first_name": "",
            "last_name": "",
            "bio": "",
            "avatar_url": "",
            "timezone": "UTC",
            "profile_complete": False,
            "is_guest": is_guest,
            "created_at": now,
            "updated_at": now,
        }
        _store['users'][user_id] = item
        _store['user_notes'][user_id] = set()

        # Create default categories
        for name, color in [("Personal", "#6366f1"), ("Work", "#10b981"), ("Ideas", "#f59e0b")]:
            create_category(user_id=user_id, name=name, color=color)

        return item

    def update_user(user_id, **fields):
        fields["updated_at"] = _now()
        if user_id in _store['users']:
            _store['users'][user_id].update(fields)

    def migrate_guest_to_cognito(user_id, cognito_sub, email, display_name):
        """Convert a guest user to a full Cognito user."""
        update_user(
            user_id,
            cognito_sub=cognito_sub,
            email=email,
            display_name=display_name,
            is_guest=False,
        )

    def delete_user(user_id):
        """Delete a user and all their data."""
        # Clean up categories, notes, attachments
        to_del = [(uid, cid) for uid, cid in _store['categories'] if uid == user_id]
        for key in to_del:
            _store['categories'].pop(key, None)
        to_del_notes = list(_store['user_notes'].get(user_id, []))
        for nid in to_del_notes:
            note = _store['notes'].get(nid)
            if note and note.get("share_token"):
                _store['shares'].pop(note["share_token"], None)
            _delete_note_children(nid)
            _store['notes'].pop(nid, None)
        _store['users'].pop(user_id, None)
        _store['user_notes'].pop(user_id, None)

    # Categories
    def list_categories(user_id):
        cats = [c for (uid, cid), c in _store['categories'].items() if uid == user_id]
        cats.sort(key=lambda x: x.get("name", ""))
        return cats

    def create_category(*, user_id, name, color="#6366f1"):
        cat_id = _new_id()
        now = _now()
        item = {
            "cat_id": cat_id,
            "name": name,
            "color": color,
            "created_at": now,
        }
        _store['categories'][(user_id, cat_id)] = item
        return item

    def delete_category(user_id, cat_id):
        _store['categories'].pop((user_id, cat_id), None)
        # Unlink notes
        for nid in list(_store['user_notes'].get(user_id, [])):
            note = _store['notes'].get(nid)
            if note and note.get("category_id") == cat_id:
                note["category_id"] = ""

    # Notes
    def list_notes(user_id, *, archived=False, search=None, category_id=None):
        notes = [_store['notes'][nid] for nid in _store['user_notes'].get(user_id, [])]
        filtered = []
        for n in notes:
            if n.get("is_archived", False) != archived:
                continue
            if category_id and n.get("category_id") != category_id:
                continue
            if search:
                term = search.lower()
                if term not in n.get("title", "").lower() and term not in n.get("content", "").lower():
                    continue
            filtered.append(n)

        # Resolve category names and add ID mapping for template compatibility
        categories = {c["cat_id"]: c for c in list_categories(user_id)}
        for n in filtered:
            cat = categories.get(n.get("category_id", ""))
            n["category_name"] = cat["name"] if cat else None
            n["category_color"] = cat["color"] if cat else None
            n["id"] = n.get("note_id")  # Template compat: note.id -> note.note_id

        # Sort: pinned first, then by updated_at descending
        filtered.sort(key=lambda x: (not x.get("is_pinned", False), x.get("updated_at", "")), reverse=False)
        filtered.sort(key=lambda x: x.get("is_pinned", False), reverse=True)
        return filtered

    def get_note(user_id, note_id):
        note = _store['notes'].get(note_id)
        if note:
            categories = {c["cat_id"]: c for c in list_categories(user_id)}
            cat = categories.get(note.get("category_id", ""))
            note["category_name"] = cat["name"] if cat else None
            note["category_color"] = cat["color"] if cat else None
        return note

    def create_note(*, user_id, title="", content="", category_id=None):
        note_id = _new_id()
        now = _now()
        item = {
            "note_id": note_id,
            "title": title,
            "content": content,
            "category_id": category_id or "",
            "is_pinned": False,
            "is_archived": False,
            "is_public": False,
            "share_token": "",
            "created_at": now,
            "updated_at": now,
        }
        _store['notes'][note_id] = item
        _store['user_notes'].setdefault(user_id, set()).add(note_id)
        return item

    def update_note(user_id, note_id, **fields):
        fields["updated_at"] = _now()
        if note_id in _store['notes']:
            _store['notes'][note_id].update(fields)

    def delete_note(user_id, note_id):
        note = _store['notes'].get(note_id)
        if note and note.get("share_token"):
            _store['shares'].pop(note["share_token"], None)
        _delete_note_children(note_id)
        _store['notes'].pop(note_id, None)
        _store['user_notes'].get(user_id, set()).discard(note_id)

    def toggle_pin(user_id, note_id):
        note = _store['notes'].get(note_id)
        if note:
            note["is_pinned"] = not note.get("is_pinned", False)

    def toggle_archive(user_id, note_id):
        note = _store['notes'].get(note_id)
        if note:
            note["is_archived"] = not note.get("is_archived", False)
            if note["is_archived"]:
                note["is_pinned"] = False

    def share_note(user_id, note_id):
        note = _store['notes'].get(note_id)
        if not note:
            return None
        token = note.get("share_token") or _secrets.token_urlsafe(32)
        note["is_public"] = True
        note["share_token"] = token
        _store['shares'][token] = (user_id, note_id)
        return token

    def unshare_note(user_id, note_id):
        note = _store['notes'].get(note_id)
        if note and note.get("share_token"):
            _store['shares'].pop(note["share_token"], None)
        note["is_public"] = False

    def get_shared_note(token):
        ptr = _store['shares'].get(token)
        if not ptr:
            return None
        user_id, note_id = ptr
        return get_note(user_id, note_id)

    # Attachments
    def list_attachments(note_id):
        atts = [a for (nid, aid), a in _store['attachments'].items() if nid == note_id]
        return atts

    def create_attachment(*, note_id, filename, s3_key, file_type, file_size):
        att_id = _new_id()
        now = _now()
        item = {
            "att_id": att_id,
            "note_id": note_id,
            "filename": filename,
            "s3_key": s3_key,
            "file_type": file_type,
            "file_size": file_size,
            "created_at": now,
        }
        _store['attachments'][(note_id, att_id)] = item
        return item

    def get_attachment(note_id, att_id):
        return _store['attachments'].get((note_id, att_id))

    def delete_attachment(note_id, att_id):
        _store['attachments'].pop((note_id, att_id), None)

    def _delete_note_children(note_id):
        """Delete all attachments for a note."""
        to_del = [(nid, aid) for nid, aid in _store['attachments'] if nid == note_id]
        for key in to_del:
            _store['attachments'].pop(key, None)

    # Stats
    def get_stats(user_id):
        notes = [_store['notes'][nid] for nid in _store['user_notes'].get(user_id, [])]
        total = len(notes)
        active = sum(1 for n in notes if not n.get("is_archived", False))
        pinned = sum(1 for n in notes if n.get("is_pinned", False))
        archived = sum(1 for n in notes if n.get("is_archived", False))
        total_chars = sum(len(n.get("content", "")) for n in notes)
        cats = list_categories(user_id)
        return {
            "total_notes": total,
            "active_notes": active,
            "pinned_notes": pinned,
            "archived_notes": archived,
            "total_characters": total_chars,
            "total_categories": len(cats),
        }

else:
    # =========================================================================
    # REAL DYNAMODB
    # =========================================================================
    import boto3
    from boto3.dynamodb.conditions import Key, Attr

    _table = None

    def _get_table():
        global _table
        if _table is None:
            dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
            _table = dynamodb.Table(TABLE_NAME)
        return _table

    def _query_all(**kwargs):
        table = _get_table()
        items = []
        start_key = None

        while True:
            query_kwargs = dict(kwargs)
            if start_key:
                query_kwargs['ExclusiveStartKey'] = start_key
            resp = table.query(**query_kwargs)
            items.extend(resp.get('Items', []))
            start_key = resp.get('LastEvaluatedKey')
            if not start_key:
                break

        return items

    def _now():
        return datetime.now(timezone.utc).isoformat()

    def _new_id():
        return uuid.uuid4().hex[:12]

    # Users
    def get_user(user_id):
        table = _get_table()
        resp = table.get_item(Key={"PK": f"USER#{user_id}", "SK": "PROFILE"})
        return resp.get("Item")

    def get_user_by_cognito_sub(cognito_sub):
        table = _get_table()
        resp = table.query(
            IndexName="GSI1",
            KeyConditionExpression=Key("GSI1PK").eq(f"COGNITO#{cognito_sub}"),
            Limit=1,
        )
        items = resp.get("Items", [])
        return items[0] if items else None

    def create_user(*, cognito_sub=None, email="", display_name="User", is_guest=False):
        table = _get_table()
        user_id = cognito_sub if cognito_sub else f"guest_{_new_id()}"
        now = _now()

        item = {
            "PK": f"USER#{user_id}",
            "SK": "PROFILE",
            "user_id": user_id,
            "cognito_sub": cognito_sub or "",
            "email": email,
            "display_name": display_name,
            "first_name": "",
            "last_name": "",
            "bio": "",
            "avatar_url": "",
            "timezone": "UTC",
            "profile_complete": False,
            "is_guest": is_guest,
            "created_at": now,
            "updated_at": now,
        }

        if cognito_sub:
            item["GSI1PK"] = f"COGNITO#{cognito_sub}"
            item["GSI1SK"] = "PROFILE"

        table.put_item(Item=item)

        # Create default categories
        for name, color in [("Personal", "#6366f1"), ("Work", "#10b981"), ("Ideas", "#f59e0b")]:
            create_category(user_id=user_id, name=name, color=color)

        return item

    def update_user(user_id, **fields):
        table = _get_table()
        fields["updated_at"] = _now()

        expr_parts = []
        names = {}
        values = {}
        for i, (k, v) in enumerate(fields.items()):
            alias = f"#f{i}"
            val_alias = f":v{i}"
            expr_parts.append(f"{alias} = {val_alias}")
            names[alias] = k
            values[val_alias] = v

        table.update_item(
            Key={"PK": f"USER#{user_id}", "SK": "PROFILE"},
            UpdateExpression="SET " + ", ".join(expr_parts),
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )

    def migrate_guest_to_cognito(user_id, cognito_sub, email, display_name):
        update_user(
            user_id,
            cognito_sub=cognito_sub,
            email=email,
            display_name=display_name,
            is_guest=False,
            GSI1PK=f"COGNITO#{cognito_sub}",
            GSI1SK="PROFILE",
        )

    def delete_user(user_id):
        table = _get_table()
        resp = _query_all(KeyConditionExpression=Key("PK").eq(f"USER#{user_id}"))
        with table.batch_writer() as batch:
            for item in resp:
                if item["SK"].startswith("NOTE#"):
                    note_id = item["SK"].split("#", 1)[1]
                    if item.get("share_token"):
                        batch.delete_item(Key={"PK": f"SHARE#{item['share_token']}", "SK": "META"})
                    _delete_note_children(note_id)
                batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})

    # Categories
    def list_categories(user_id):
        items = _query_all(
            KeyConditionExpression=Key("PK").eq(f"USER#{user_id}") & Key("SK").begins_with("CAT#"),
        )
        items.sort(key=lambda x: x.get("name", ""))
        return items

    def create_category(*, user_id, name, color="#6366f1"):
        table = _get_table()
        cat_id = _new_id()
        now = _now()

        item = {
            "PK": f"USER#{user_id}",
            "SK": f"CAT#{cat_id}",
            "cat_id": cat_id,
            "name": name,
            "color": color,
            "created_at": now,
        }
        table.put_item(Item=item)
        return item

    def delete_category(user_id, cat_id):
        table = _get_table()
        table.delete_item(Key={"PK": f"USER#{user_id}", "SK": f"CAT#{cat_id}"})
        notes = list_notes(user_id)
        for note in notes:
            if note.get("category_id") == cat_id:
                update_note(user_id, note["note_id"], category_id="")

    # Notes
    def list_notes(user_id, *, archived=False, search=None, category_id=None):
        items = _query_all(
            KeyConditionExpression=Key("PK").eq(f"USER#{user_id}") & Key("SK").begins_with("NOTE#"),
        )

        filtered = []
        for n in items:
            if n.get("is_archived", False) != archived:
                continue
            if category_id and n.get("category_id") != category_id:
                continue
            if search:
                term = search.lower()
                if term not in n.get("title", "").lower() and term not in n.get("content", "").lower():
                    continue
            filtered.append(n)

        categories = {c["cat_id"]: c for c in list_categories(user_id)}
        for n in filtered:
            cat = categories.get(n.get("category_id", ""))
            n["category_name"] = cat["name"] if cat else None
            n["category_color"] = cat["color"] if cat else None
            n["id"] = n.get("note_id")  # Template compat: note.id -> note.note_id

        filtered.sort(key=lambda x: (not x.get("is_pinned", False), x.get("updated_at", "")), reverse=False)
        filtered.sort(key=lambda x: x.get("is_pinned", False), reverse=True)

        return filtered

    def get_note(user_id, note_id):
        table = _get_table()
        resp = table.get_item(Key={"PK": f"USER#{user_id}", "SK": f"NOTE#{note_id}"})
        item = resp.get("Item")
        if item:
            categories = {c["cat_id"]: c for c in list_categories(user_id)}
            cat = categories.get(item.get("category_id", ""))
            item["category_name"] = cat["name"] if cat else None
            item["category_color"] = cat["color"] if cat else None
        return item

    def create_note(*, user_id, title="", content="", category_id=None):
        table = _get_table()
        note_id = _new_id()
        now = _now()

        item = {
            "PK": f"USER#{user_id}",
            "SK": f"NOTE#{note_id}",
            "note_id": note_id,
            "title": title,
            "content": content,
            "category_id": category_id or "",
            "is_pinned": False,
            "is_archived": False,
            "is_public": False,
            "share_token": "",
            "created_at": now,
            "updated_at": now,
        }
        table.put_item(Item=item)
        return item

    def update_note(user_id, note_id, **fields):
        table = _get_table()
        fields["updated_at"] = _now()

        expr_parts = []
        names = {}
        values = {}
        for i, (k, v) in enumerate(fields.items()):
            alias = f"#f{i}"
            val_alias = f":v{i}"
            expr_parts.append(f"{alias} = {val_alias}")
            names[alias] = k
            values[val_alias] = v

        table.update_item(
            Key={"PK": f"USER#{user_id}", "SK": f"NOTE#{note_id}"},
            UpdateExpression="SET " + ", ".join(expr_parts),
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )

    def delete_note(user_id, note_id):
        table = _get_table()
        note = get_note(user_id, note_id)
        if note and note.get("share_token"):
            table.delete_item(Key={"PK": f"SHARE#{note['share_token']}", "SK": "META"})

        _delete_note_children(note_id)
        table.delete_item(Key={"PK": f"USER#{user_id}", "SK": f"NOTE#{note_id}"})

    def toggle_pin(user_id, note_id):
        note = get_note(user_id, note_id)
        if note:
            update_note(user_id, note_id, is_pinned=not note.get("is_pinned", False))

    def toggle_archive(user_id, note_id):
        note = get_note(user_id, note_id)
        if note:
            update_note(user_id, note_id, is_archived=not note.get("is_archived", False), is_pinned=False)

    def share_note(user_id, note_id):
        note = get_note(user_id, note_id)
        if not note:
            return None

        token = note.get("share_token") or _secrets.token_urlsafe(32)
        update_note(user_id, note_id, is_public=True, share_token=token)

        table = _get_table()
        table.put_item(Item={
            "PK": f"SHARE#{token}",
            "SK": "META",
            "user_id": user_id,
            "note_id": note_id,
        })
        return token

    def unshare_note(user_id, note_id):
        note = get_note(user_id, note_id)
        if note and note.get("share_token"):
            table = _get_table()
            table.delete_item(Key={"PK": f"SHARE#{note['share_token']}", "SK": "META"})
        update_note(user_id, note_id, is_public=False)

    def get_shared_note(token):
        table = _get_table()
        resp = table.get_item(Key={"PK": f"SHARE#{token}", "SK": "META"})
        pointer = resp.get("Item")
        if not pointer:
            return None

        note = get_note(pointer["user_id"], pointer["note_id"])
        if note and note.get("is_public"):
            return note
        return None

    # Attachments
    def list_attachments(note_id):
        items = _query_all(
            KeyConditionExpression=Key("PK").eq(f"NOTE#{note_id}") & Key("SK").begins_with("ATT#"),
        )
        return items

    def create_attachment(*, note_id, filename, s3_key, file_type, file_size):
        table = _get_table()
        att_id = _new_id()
        now = _now()

        item = {
            "PK": f"NOTE#{note_id}",
            "SK": f"ATT#{att_id}",
            "att_id": att_id,
            "note_id": note_id,
            "filename": filename,
            "s3_key": s3_key,
            "file_type": file_type,
            "file_size": file_size,
            "created_at": now,
        }
        table.put_item(Item=item)
        return item

    def get_attachment(note_id, att_id):
        table = _get_table()
        resp = table.get_item(Key={"PK": f"NOTE#{note_id}", "SK": f"ATT#{att_id}"})
        return resp.get("Item")

    def delete_attachment(note_id, att_id):
        table = _get_table()
        table.delete_item(Key={"PK": f"NOTE#{note_id}", "SK": f"ATT#{att_id}"})

    def _delete_note_children(note_id):
        table = _get_table()
        resp = _query_all(KeyConditionExpression=Key("PK").eq(f"NOTE#{note_id}"))
        with table.batch_writer() as batch:
            for item in resp:
                batch.delete_item(Key={"PK": item["PK"], "SK": item["SK"]})

    # Stats
    def get_stats(user_id):
        notes = _query_all(
            KeyConditionExpression=Key("PK").eq(f"USER#{user_id}") & Key("SK").begins_with("NOTE#"),
        )

        total = len(notes)
        active = sum(1 for n in notes if not n.get("is_archived", False))
        pinned = sum(1 for n in notes if n.get("is_pinned", False))
        archived = sum(1 for n in notes if n.get("is_archived", False))
        total_chars = sum(len(n.get("content", "")) for n in notes)

        cats = list_categories(user_id)

        return {
            "total_notes": total,
            "active_notes": active,
            "pinned_notes": pinned,
            "archived_notes": archived,
            "total_characters": total_chars,
            "total_categories": len(cats),
        }
