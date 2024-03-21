
-- `session` identifies individual clients with a particular set of
-- capabilities.  the `session_id` is the secret held by the client.
CREATE TABLE session (
  session_id VARCHAR NOT NULL,
  confidential BOOLEAN NOT NULL,
  created REAL NOT NULL,
  mechanism TEXT NOT NULL,
  PRIMARY KEY (session_id)
);

-- `account` is a user with a name and password.  the password_blob is computed
-- by the password engine in klein.storage.passwords.
CREATE TABLE account (
  account_id VARCHAR NOT NULL,
  username VARCHAR NOT NULL,
  email VARCHAR NOT NULL,
  password_blob VARCHAR NOT NULL,
  PRIMARY KEY (account_id),
  UNIQUE (username)
);

-- `session_account` is a record of which acccount is logged in to which session.
CREATE TABLE session_account (
  account_id VARCHAR,
  session_id VARCHAR,
  UNIQUE (account_id, session_id),
  FOREIGN KEY(account_id)
    REFERENCES account (account_id)
    ON DELETE CASCADE,
  FOREIGN KEY(session_id)
    REFERENCES session (session_id)
    ON DELETE CASCADE
);
