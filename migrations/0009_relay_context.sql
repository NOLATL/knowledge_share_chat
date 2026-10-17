-- Context shown to the relay recipient: what a complete answer to the
-- delegated question includes (generated at send time).
ALTER TABLE email_relays ADD COLUMN context_text text;
