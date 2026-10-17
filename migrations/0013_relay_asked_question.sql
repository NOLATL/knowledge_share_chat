-- The actual question the interviewer asked in chat (cleaned to stand alone),
-- so the relay email and landing page match the conversation instead of the
-- scripted template. NULL falls back to questions.text for older relays.
ALTER TABLE email_relays ADD COLUMN asked_question_text text;
