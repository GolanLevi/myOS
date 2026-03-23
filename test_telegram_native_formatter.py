import unittest

from bot.message_formatter import (
    CALLBACK_DATA_LIMIT,
    MANUAL_OVERRIDE_TEXT,
    build_callback_data,
    prepare_message,
    prepare_server_response,
)


class TelegramNativeFormatterTests(unittest.TestCase):
    def test_build_callback_data_embeds_thread_and_stays_within_limit(self) -> None:
        callback = build_callback_data("approve this", "thread-123")

        self.assertTrue(callback.startswith("approve_this::thread-123"))
        self.assertLessEqual(len(callback.encode("utf-8")), CALLBACK_DATA_LIMIT)

    def test_prepare_message_parses_button_marker_and_scopes_callbacks_to_thread(self) -> None:
        prepared = prepare_message(
            "Line 1\n\n[[BUTTONS: אשר | בטל | אני אגיב ידנית]]",
            thread_id="thread-123",
        )

        self.assertEqual(prepared.text, "Line 1")
        self.assertEqual(
            [button.text for button in prepared.buttons],
            ["✅ אשר", "❌ בטל", MANUAL_OVERRIDE_TEXT],
        )
        self.assertTrue(all(button.callback_data.endswith("::thread-123") for button in prepared.buttons))
        self.assertEqual(prepared.buttons[-1].callback_data, "אני_אגיב_ידנית::thread-123")

    def test_prepare_message_maps_new_manual_guidance_label_to_legacy_callback(self) -> None:
        prepared = prepare_message(
            "Line 1\n\n[[BUTTONS: אשר | בטל | אתן הכוונה]]",
            thread_id="thread-124",
        )

        self.assertEqual(
            [button.text for button in prepared.buttons],
            ["✅ אשר", "❌ בטל", MANUAL_OVERRIDE_TEXT],
        )
        self.assertEqual(prepared.buttons[-1].callback_data, "אני_אגיב_ידנית::thread-124")

    def test_prepare_server_response_uses_fallback_buttons_for_paused_meeting(self) -> None:
        prepared = prepare_server_response(
            {
                "answer": "הודעה לגבי פגישה מחר בבוקר",
                "internal_id": "thread-55",
                "is_paused": True,
            }
        )

        self.assertEqual(prepared.text, "הודעה לגבי פגישה מחר בבוקר")
        self.assertEqual(
            [button.text for button in prepared.buttons],
            ["📅 אשר וסנכרן ליומן", "🙏 דחה בנימוס", MANUAL_OVERRIDE_TEXT],
        )
        self.assertTrue(all(button.callback_data.endswith("::thread-55") for button in prepared.buttons))
        self.assertEqual(prepared.parse_mode, "HTML")

    def test_prepare_server_response_preserves_explicit_buttons_from_legacy_shape(self) -> None:
        prepared = prepare_server_response(
            {
                "answer": "הטקסט כבר מוכן",
                "internal_id": "thread-77",
                "reply_markup": {
                    "inline_keyboard": [
                        [{"text": "אשר", "callback_data": "approve::thread-77"}],
                        [{"text": "בטל", "callback_data": "reject::thread-77"}],
                    ]
                },
            }
        )

        self.assertEqual(prepared.text, "הטקסט כבר מוכן")
        self.assertEqual(
            [(button.text, button.callback_data) for button in prepared.buttons],
            [("✅ אשר", "approve::thread-77"), ("❌ בטל", "reject::thread-77")],
        )

    def test_prepare_server_response_builds_buttons_from_slim_contract(self) -> None:
        prepared = prepare_server_response(
            {
                "status": "success",
                "answer": "שלום, בוצע",
                "internal_id": "thread-88",
                "is_paused": False,
                "suggested_buttons": ["אשר", "בטל", "אני אגיב ידנית"],
            }
        )

        self.assertEqual(prepared.text, "שלום, בוצע")
        self.assertEqual(
            [button.text for button in prepared.buttons],
            ["✅ אשר", "❌ בטל", MANUAL_OVERRIDE_TEXT],
        )
        self.assertTrue(all(button.callback_data.endswith("::thread-88") for button in prepared.buttons))

    def test_prepare_server_response_converts_markdown_bold_to_html(self) -> None:
        prepared = prepare_server_response(
            {
                "answer": "📧 *שליחת מייל לאישורך*\n*נושא*: פגישה",
                "internal_id": "thread-99",
                "is_paused": True,
            }
        )

        self.assertEqual(prepared.parse_mode, "HTML")
        self.assertIn("<b>שליחת מייל לאישורך</b>", prepared.text)
        self.assertIn("<b>נושא</b>: פגישה", prepared.text)

    def test_prepare_server_response_converts_double_asterisk_bold_to_html(self) -> None:
        prepared = prepare_server_response(
            {
                "answer": "**Approved**\n**Subject**: Meeting",
                "internal_id": "thread-100",
                "is_paused": True,
            }
        )

        self.assertIn("<b>Approved</b>", prepared.text)
        self.assertIn("<b>Subject</b>: Meeting", prepared.text)

    def test_prepare_server_response_ignores_marker_buttons_on_non_paused_message(self) -> None:
        prepared = prepare_server_response(
            {
                "answer": "Action completed successfully.\n[[BUTTONS: Approve | Reject | Manual]]",
                "internal_id": "thread-101",
                "is_paused": False,
            }
        )

        self.assertEqual(prepared.buttons, [])
        self.assertEqual(prepared.text, "Action completed successfully.")

    def test_prepare_server_response_keeps_marker_buttons_for_non_terminal_draft(self) -> None:
        prepared = prepare_server_response(
            {
                "answer": "Draft ready.\n[[BUTTONS: אשר ושלח | דחה בנימוס | אני אגיב ידנית]]",
                "internal_id": "thread-102",
                "is_paused": False,
            }
        )

        self.assertEqual(
            [button.text for button in prepared.buttons],
            ["✅ אשר ושלח", "🙏 דחה בנימוס", MANUAL_OVERRIDE_TEXT],
        )
        self.assertEqual(prepared.text, "Draft ready.")


if __name__ == "__main__":
    unittest.main()
