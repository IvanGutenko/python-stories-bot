import os
import asyncio
import random
import time
import python_socks
from telethon import TelegramClient, functions, types, errors
from telethon.tl.types import (
    MediaAreaUrl,
    MediaAreaCoordinates,
    InputMediaUploadedPhoto,
    InputMediaUploadedDocument,
    InputPrivacyValueAllowUsers,
    MessageEntityMention,
    MessageEntityMentionName,
    DocumentAttributeVideo,
    InputUser,
)
from telethon.tl.functions.messages import SetHistoryTTLRequest
import config


async def get_sessions():
    sessions = []
    if not os.path.exists(config.SESSIONS_DIR):
        os.makedirs(config.SESSIONS_DIR)
    for file in os.listdir(config.SESSIONS_DIR):
        if file.endswith('.session'):
            sessions.append(os.path.join(config.SESSIONS_DIR, file))
    return sessions


async def _random_delay(min_sec: float, max_sec: float, label: str = "") -> float:
    delay = random.uniform(min_sec, max_sec)
    if label:
        print(f"⏳ [{label}] Waiting {delay:.1f}s...")
    await asyncio.sleep(delay)
    return delay


def _get_proxy():
    proxy_settings = None
    if getattr(config, 'USE_PROXY', False):
        p_type = python_socks.ProxyType.SOCKS5 if config.PROXY_TYPE == 'socks5' else python_socks.ProxyType.HTTP
        proxy_settings = {
            'proxy_type': p_type,
            'addr': config.PROXY_IP,
            'port': int(config.PROXY_PORT),
            'username': config.PROXY_USER,
            'password': config.PROXY_PASS,
            'rdns': True
        }
    return proxy_settings


def _create_client(session_path: str):
    return TelegramClient(
        session_path,
        config.API_ID,
        config.API_HASH,
        proxy=_get_proxy(),
        device_model="iPhone 15 Pro",
        system_version="17.4.1",
        app_version="10.12.0",
        lang_code="en",
        system_lang_code="en-US"
    )


class StoryPublisher:
    """
    Unified story publisher v4.
    
    Single pipeline:
    1. init_dialogs_ttl() - Инициализация диалогов через TTL
    2. ttl_delay() - Пауза для регистрации диалогов Telegram
    3. resolve_and_prepare() - Резолвим пользователей, контакты
    4. publish_with_mentions() - Публикация закрытой сториз с упоминаниями
    5. verify_and_edit() - Backup re-edit
    6. cleanup() - Убираем контакты
    """

    def __init__(self, client: TelegramClient, media_path: str, link_url: str = None):
        self.client = client
        self.media_path = media_path
        self.link_url = link_url

        self.input_peers = []
        self.input_users = []
        self.full_users = []
        self.entities_mention = []
        self.entities_mention_name = []
        self.caption_parts = []
        self.added_contacts_ids = []
        self.tagged_users = []
        self.story_id = None
        self.story_username = None
        self.dialogs_initiated = 0

    async def init_dialogs_ttl(self, users_chunk: list) -> int:
        """
        PHASE 1: Инициализация диалогов через SetHistoryTTL.
        Создаёт диалог без отправки сообщений.
        """
        print("\n" + "=" * 60)
        print("🔗 PHASE 1: DIALOG INITIALIZATION (TTL)")
        print("=" * 60)

        initiated = 0

        for i, username in enumerate(users_chunk):
            username_clean = username.strip().replace('@', '')
            print(f"\n🔄 [{i + 1}/{len(users_chunk)}] TTL init @{username_clean}...")

            if i > 0:
                await _random_delay(1.5, 3.0, "anti-spam")

            try:
                entity = await self.client.get_input_entity(username_clean)

                await self.client(SetHistoryTTLRequest(
                    peer=entity,
                    period=31536000  # 1 год
                ))

                print(f"   ✅ TTL set for @{username_clean}")
                initiated += 1

            except errors.UsernameNotOccupiedError:
                print(f"   ❌ @{username_clean} — not found")
            except errors.UsernameInvalidError:
                print(f"   ❌ @{username_clean} — invalid")
            except Exception as e:
                print(f"   ❌ @{username_clean} — {type(e).__name__}: {e}")

        self.dialogs_initiated = initiated
        print(f"\n📊 TTL initialized: {initiated}/{len(users_chunk)}")
        return initiated

    async def ttl_delay(self):
        """
        PHASE 2: Пауза после TTL для регистрации диалогов в системе Telegram.
        """
        print("\n" + "=" * 60)
        print("⏳ PHASE 2: TTL REGISTRATION DELAY")
        print("=" * 60)

        delay_seconds = getattr(config, 'TTL_TO_PUBLISH_DELAY', 300)
        print(f"⏱ Waiting {delay_seconds}s for Telegram to register dialogs...")
        await asyncio.sleep(delay_seconds)
        print(f"✅ TTL delay complete")

    async def resolve_and_prepare(self, users_chunk: list) -> list:
        """
        PHASE 3: Resolve users, get full user objects, add to contacts.
        """
        print("\n" + "=" * 60)
        print("📱 PHASE 3: RESOLVE USERS & PREPARE")
        print("=" * 60)

        max_tags = getattr(config, 'MAX_TAGS_PER_STORY', 3)
        limited_users = users_chunk[:max_tags]
        resolved = []

        for i, username in enumerate(limited_users):
            username_clean = username.strip().replace('@', '')
            print(f"\n🔄 [{i + 1}/{len(limited_users)}] Resolving @{username_clean}...")

            if i > 0:
                await _random_delay(1.0, 2.0, "between-users")

            try:
                entity = await self.client.get_input_entity(username_clean)
                full_user = await self.client.get_entity(username_clean)

                user_id = None
                access_hash = None

                if hasattr(entity, 'user_id'):
                    user_id = entity.user_id
                if hasattr(entity, 'access_hash'):
                    access_hash = entity.access_hash
                if hasattr(full_user, 'id'):
                    user_id = full_user.id
                if hasattr(full_user, 'access_hash'):
                    access_hash = full_user.access_hash

                if not user_id:
                    print(f"   ⚠️ Could not resolve user_id")
                    continue

                print(f"   📋 user_id: {user_id}")

                # Добавляем в контакты
                try:
                    await self.client(functions.contacts.AddContactRequest(
                        id=entity,
                        first_name=username_clean[:20],
                        last_name="",
                        phone="",
                        add_phone_privacy_exception=False
                    ))
                    self.added_contacts_ids.append(user_id)
                    print(f"   ✅ Added to contacts")
                except Exception as e:
                    print(f"   ⚠️ Contact add: {type(e).__name__}")

                self.input_peers.append(entity)
                self.full_users.append(full_user)

                if access_hash is not None:
                    self.input_users.append(InputUser(
                        user_id=user_id,
                        access_hash=access_hash
                    ))

                user_info = {
                    'username': username_clean,
                    'user_id': user_id,
                    'access_hash': access_hash,
                    'entity': entity,
                }
                self.tagged_users.append(user_info)
                resolved.append(user_info)

                # Build caption
                part = f"@{username_clean}"
                current_offset = sum(len(p) + 1 for p in self.caption_parts)
                self.caption_parts.append(part)

                self.entities_mention.append(MessageEntityMention(
                    offset=current_offset,
                    length=len(part)
                ))

                self.entities_mention_name.append(MessageEntityMentionName(
                    offset=current_offset,
                    length=len(part),
                    user_id=user_id
                ))

                print(f"   ✅ Resolved")

            except errors.UsernameNotOccupiedError:
                print(f"   ❌ Username does not exist")
            except errors.UsernameInvalidError:
                print(f"   ❌ Invalid username")
            except Exception as e:
                print(f"   ❌ Error: {type(e).__name__}: {e}")

        print(f"\n📊 Resolved: {len(resolved)}/{len(limited_users)}")
        return resolved

    async def _upload_media(self):
        print("📁 Uploading media...")
        uploaded_file = await self.client.upload_file(self.media_path)
        ext = os.path.splitext(self.media_path)[1].lower()
        if ext in ['.jpg', '.jpeg', '.png', '.webp']:
            return InputMediaUploadedPhoto(file=uploaded_file)
        else:
            return InputMediaUploadedDocument(
                file=uploaded_file,
                mime_type='video/mp4',
                attributes=[DocumentAttributeVideo(duration=0, w=0, h=0)]
            )

    async def _get_media_areas(self):
        media_areas = []
        if self.link_url:
            media_areas.append(MediaAreaUrl(
                coordinates=MediaAreaCoordinates(
                    x=50.0, y=90.0, w=30.0, h=10.0, rotation=0.0
                ),
                url=self.link_url
            ))
        return media_areas

    def _extract_story_id(self, result):
        if hasattr(result, 'id'):
            return result.id
        if hasattr(result, 'story'):
            return result.story.id
        if hasattr(result, 'updates'):
            for update in result.updates:
                if hasattr(update, 'story') and hasattr(update.story, 'id'):
                    return update.story.id
        return None

    async def publish_with_mentions(self) -> bool:
        """
        PHASE 4: Публикуем ЗАКРЫТУЮ сториз с упоминаниями.
        Privacy: только упомянутые пользователи видят историю.
        """
        print("\n" + "=" * 60)
        print("📤 PHASE 4: PUBLISH CLOSED STORY WITH MENTIONS")
        print("=" * 60)

        if not self.input_peers:
            print("❌ No valid users")
            return False

        media_content = await self._upload_media()
        media_areas = await self._get_media_areas()

        try:
            me = await self.client.get_me()
            self.story_username = me.username
            is_premium = getattr(me, 'premium', False)
            print(f"👤 Account: {me.first_name} | Premium: {is_premium}")
        except:
            pass

        final_caption = " ".join(self.caption_parts)
        entities_to_use = self.entities_mention_name

        print(f"📝 Caption: {final_caption}")
        print(f"🏷️ Entities: {len(entities_to_use)} MentionName")
        print(f"🔒 Privacy: AllowUsers only (closed story)")
        for ent in entities_to_use:
            print(f"   → user_id: {ent.user_id}, offset: {ent.offset}, length: {ent.length}")

        # ЗАКРЫТАЯ история — только упомянутые видят
        privacy_rules = [InputPrivacyValueAllowUsers(users=self.input_peers)]

        print(f"\n📤 Publishing closed story with MentionName entities...")

        try:
            result = await self.client(functions.stories.SendStoryRequest(
                peer='me',
                media=media_content,
                media_areas=media_areas if media_areas else None,
                privacy_rules=privacy_rules,
                period=86400,
                caption=final_caption,
                entities=entities_to_use
            ))

            self.story_id = self._extract_story_id(result)

            if self.story_id:
                print(f"✅ Closed story published (ID: {self.story_id})")
                return True
            else:
                print(f"⚠️ Published but no ID extracted")
                return False

        except Exception as e:
            print(f"❌ MentionName failed: {type(e).__name__}: {e}")

            # Fallback: @mention entities
            print(f"\n📤 Fallback: @mention entities...")
            try:
                media_content2 = await self._upload_media()

                result = await self.client(functions.stories.SendStoryRequest(
                    peer='me',
                    media=media_content2,
                    media_areas=media_areas if media_areas else None,
                    privacy_rules=privacy_rules,
                    period=86400,
                    caption=final_caption,
                    entities=self.entities_mention
                ))

                self.story_id = self._extract_story_id(result)

                if self.story_id:
                    print(f"✅ Fallback story published (ID: {self.story_id})")
                    return True
                return False

            except Exception as e2:
                print(f"❌ Fallback also failed: {type(e2).__name__}: {e2}")
                return False

    async def verify_and_edit(self) -> bool:
        """
        PHASE 5: Backup re-edit для дополнительного триггера уведомлений.
        """
        print("\n" + "=" * 60)
        print("✏️ PHASE 5: VERIFY & RE-EDIT")
        print("=" * 60)

        if not self.story_id:
            print("⚠️ No story to edit")
            return False

        await _random_delay(30, 60, "pre-edit-delay")

        final_caption = " ".join(self.caption_parts)

        print(f"✏️ Re-editing with MentionName...")
        try:
            result = await self.client(functions.stories.EditStoryRequest(
                peer='me',
                id=self.story_id,
                caption=final_caption,
                entities=self.entities_mention_name
            ))
            print(f"✅ Edit result: {type(result).__name__}")
        except errors.StoryNotModifiedError:
            print("ℹ️ Story not modified (same content — OK)")
        except Exception as e:
            print(f"⚠️ Edit failed: {type(e).__name__}: {e}")

            try:
                alt_caption = final_caption + " "
                alt_entities = []
                for part_idx, info in enumerate(self.tagged_users):
                    part = f"@{info['username']}"
                    offset = sum(len(f"@{self.tagged_users[j]['username']}") + 1 for j in range(part_idx))
                    alt_entities.append(MessageEntityMention(offset=offset, length=len(part)))

                await self.client(functions.stories.EditStoryRequest(
                    peer='me',
                    id=self.story_id,
                    caption=alt_caption,
                    entities=alt_entities
                ))
                print(f"✅ Fallback edit OK")
            except Exception as e2:
                print(f"⚠️ Fallback edit failed: {e2}")

        return True

    async def cleanup(self):
        """
        PHASE 6: Cleanup contacts after push delivery window.
        """
        print("\n" + "=" * 60)
        print("🧹 PHASE 6: CLEANUP")
        print("=" * 60)

        delay = await _random_delay(120, 240, "push-delivery-window")
        print(f"📬 Push delivery window: {delay:.1f}s")

        if self.added_contacts_ids:
            try:
                await self.client(functions.contacts.DeleteContactsRequest(
                    id=self.added_contacts_ids
                ))
                print(f"🗑️ Removed {len(self.added_contacts_ids)} contacts")
            except Exception as e:
                print(f"⚠️ Contact cleanup: {e}")

        print("✅ Cleanup complete")


async def send_story_with_init(session_path: str, users_chunk: list, media_path: str, link_url: str = None):
    """
    Unified pipeline v4 — всё в одном вызове:
    1. TTL init dialogs
    2. TTL delay  
    3. Resolve & prepare
    4. Publish closed story with mentions
    5. Verify & re-edit
    6. Cleanup
    """
    client = _create_client(session_path)

    try:
        await client.connect()
        if not await client.is_user_authorized():
            print(f"❌ Session not authorized: {session_path}")
            return {'success': False, 'error': 'not authorized'}

        me = await client.get_me()
        print(f"\n{'=' * 60}")
        print(f"🚀 STORY PIPELINE v4 (UNIFIED)")
        print(f"{'=' * 60}")
        print(f"👤 Account: {me.first_name} (@{me.username})")
        print(f"⭐ Premium: {getattr(me, 'premium', False)}")
        print(f"👥 Target users: {len(users_chunk)}")
        print(f"🔒 Story type: CLOSED (AllowUsers only)")
        print(f"{'=' * 60}")

        publisher = StoryPublisher(client, media_path, link_url)

        # PHASE 1: TTL init
        initiated = await publisher.init_dialogs_ttl(users_chunk)
        if initiated == 0:
            print("\n❌ No dialogs initialized, aborting")
            return {'success': False, 'error': 'no dialogs initialized'}

        # PHASE 2: TTL delay
        await publisher.ttl_delay()

        # PHASE 3: Resolve
        resolved = await publisher.resolve_and_prepare(users_chunk)
        if not publisher.input_peers:
            print("\n❌ No valid users resolved, aborting")
            return {'success': False, 'error': 'no users resolved'}

        # PHASE 4: Publish
        published = await publisher.publish_with_mentions()
        if not published:
            print("\n❌ Failed to publish")
            return {'success': False, 'error': 'publish failed'}

        # PHASE 5: Verify & edit
        await publisher.verify_and_edit()

        # PHASE 6: Cleanup
        await publisher.cleanup()

        print(f"\n{'=' * 60}")
        print(f"🏁 PIPELINE COMPLETE")
        print(f"{'=' * 60}")
        print(f"📸 Story ID: {publisher.story_id}")
        print(f"🔗 TTL dialogs: {publisher.dialogs_initiated}")
        print(f"👥 Tagged: {len(publisher.tagged_users)} users")
        print(f"🔒 Closed story: Yes")
        print(f"{'=' * 60}\n")

        return {
            'success': True,
            'story_id': publisher.story_id,
            'story_username': publisher.story_username,
            'tagged_users': publisher.tagged_users,
            'tags_added': published,
            'notified_count': len(resolved),
            'dialogs_initiated': publisher.dialogs_initiated
        }

    except Exception as e:
        print(f"❌ Pipeline error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}
    finally:
        await client.disconnect()