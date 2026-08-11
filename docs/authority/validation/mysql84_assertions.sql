-- R4.2 MySQL 8.4 runtime assertions
DELIMITER //
CREATE PROCEDURE assert_r4_contract()
BEGIN
  DECLARE got_error BOOLEAN DEFAULT FALSE;

  IF (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_type='BASE TABLE') <> 85 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Expected exactly 85 base tables';
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=DATABASE() AND table_name='atp_permission_code' AND column_name='role_id'
  ) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='atp_permission_code.role_id must not exist';
  END IF;
  IF (SELECT column_name FROM information_schema.key_column_usage
      WHERE table_schema=DATABASE() AND table_name='atp_credential_revision' AND constraint_name='PRIMARY'
      ORDER BY ordinal_position LIMIT 1) <> 'credential_revision_id' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='CredentialRevision primary key mismatch';
  END IF;
  IF (SELECT column_name FROM information_schema.key_column_usage
      WHERE table_schema=DATABASE() AND table_name='atp_technical_alert_endpoint' AND constraint_name='PRIMARY'
      ORDER BY ordinal_position LIMIT 1) <> 'technical_alert_endpoint_id' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='TechnicalAlertEndpoint primary key mismatch';
  END IF;
  IF (SELECT column_default FROM information_schema.columns
      WHERE table_schema=DATABASE() AND table_name='atp_run_task' AND column_name='final_result') <> 'UNKNOWN' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='RunTask final_result default mismatch';
  END IF;
  IF (SELECT COUNT(*) FROM atp_permission_code) <> 50 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Permission seed count mismatch';
  END IF;
  IF (SELECT COUNT(*) FROM atp_role) <> 12 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Role seed count mismatch';
  END IF;
  IF (SELECT COUNT(*) FROM atp_role_permission) <> 600 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Role-permission seed count mismatch';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.referential_constraints
    WHERE constraint_schema=DATABASE() AND constraint_name='fk_atp_platform_user_credential_user'
  ) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Platform credential user FK missing'; END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.referential_constraints
    WHERE constraint_schema=DATABASE() AND constraint_name='fk_atp_auth_refresh_session_credential'
  ) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Refresh session credential FK missing'; END IF;

  INSERT INTO atp_user
    (user_id,username,lifecycle_status,row_version,created_at,updated_at)
  VALUES (CONCAT('R42',LPAD('1',23,'0')),'r42_constraint_user','ACTIVE',0,CURRENT_TIMESTAMP(6),CURRENT_TIMESTAMP(6));
  INSERT INTO atp_user
    (user_id,username,lifecycle_status,row_version,created_at,updated_at)
  VALUES (CONCAT('R42',LPAD('10',23,'0')),'r42_version_check_user','ACTIVE',0,CURRENT_TIMESTAMP(6),CURRENT_TIMESTAMP(6));
  INSERT INTO atp_platform_user_credential
    (credential_id,user_id,password_hash,password_changed_at,created_at,updated_at)
  VALUES (CONCAT('R42',LPAD('2',23,'0')),CONCAT('R42',LPAD('1',23,'0')),
          '$argon2id$v=19$m=65536,t=3,p=1$TEST$TEST',CURRENT_TIMESTAMP(6),CURRENT_TIMESTAMP(6),CURRENT_TIMESTAMP(6));
  INSERT INTO atp_auth_refresh_session
    (session_id,credential_id,family_id,token_hash,credential_version,issued_at,expires_at,created_at,updated_at)
  VALUES (CONCAT('R42',LPAD('3',23,'0')),CONCAT('R42',LPAD('2',23,'0')),CONCAT('R42',LPAD('4',23,'0')),
          UNHEX(SHA2('r42-test-token',256)),1,CURRENT_TIMESTAMP(6),TIMESTAMPADD(DAY,7,CURRENT_TIMESTAMP(6)),CURRENT_TIMESTAMP(6),CURRENT_TIMESTAMP(6));

  SET got_error = FALSE;
  BEGIN
    DECLARE CONTINUE HANDLER FOR SQLEXCEPTION SET got_error = TRUE;
    INSERT INTO atp_permission_code
      (permission_code_id,permission_code,lifecycle_status,row_version,created_at,updated_at)
    VALUES ('R4DUPLICATEPERMISSION00001','PROJECT_VIEW','ACTIVE',0,CURRENT_TIMESTAMP(6),CURRENT_TIMESTAMP(6));
  END;
  IF got_error = FALSE THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Unique constraint rejection failed'; END IF;

  SET got_error = FALSE;
  BEGIN
    DECLARE CONTINUE HANDLER FOR SQLEXCEPTION SET got_error = TRUE;
    INSERT INTO atp_permission_code
      (permission_code_id,permission_code,lifecycle_status,row_version,created_at,updated_at)
    VALUES ('R4INVALIDSTATE00000000001','R4_INVALID_STATE_TEST','BROKEN',0,CURRENT_TIMESTAMP(6),CURRENT_TIMESTAMP(6));
  END;
  IF got_error = FALSE THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='CHECK constraint rejection failed'; END IF;

  SET got_error = FALSE;
  BEGIN
    DECLARE CONTINUE HANDLER FOR SQLEXCEPTION SET got_error = TRUE;
    INSERT INTO atp_role_permission(role_id,permission_id,decision,created_at)
    VALUES ('NONEXISTENTROLE0000000001','NONEXISTENTPERMISSION0001','ALLOWED',CURRENT_TIMESTAMP(6));
  END;
  IF got_error = FALSE THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Foreign-key rejection failed'; END IF;

  SET got_error = FALSE;
  BEGIN
    DECLARE CONTINUE HANDLER FOR SQLEXCEPTION SET got_error = TRUE;
    INSERT INTO atp_user
      (user_id,username,lifecycle_status,row_version,created_at,updated_at)
    VALUES (CONCAT('R42',LPAD('5',23,'0')),'r42_constraint_user','ACTIVE',0,CURRENT_TIMESTAMP(6),CURRENT_TIMESTAMP(6));
  END;
  IF got_error = FALSE THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Username unique rejection failed'; END IF;

  SET got_error = FALSE;
  BEGIN
    DECLARE CONTINUE HANDLER FOR SQLEXCEPTION SET got_error = TRUE;
    INSERT INTO atp_platform_user_credential
      (credential_id,user_id,password_hash,password_changed_at,created_at,updated_at)
    VALUES (CONCAT('R42',LPAD('6',23,'0')),CONCAT('R42',LPAD('1',23,'0')),
            '$argon2id$v=19$m=65536,t=3,p=1$TEST$TEST',CURRENT_TIMESTAMP(6),CURRENT_TIMESTAMP(6),CURRENT_TIMESTAMP(6));
  END;
  IF got_error = FALSE THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Credential unique rejection failed'; END IF;

  SET got_error = FALSE;
  BEGIN
    DECLARE CONTINUE HANDLER FOR SQLEXCEPTION SET got_error = TRUE;
    INSERT INTO atp_platform_user_credential
      (credential_id,user_id,password_hash,credential_version,password_changed_at,created_at,updated_at)
    VALUES (CONCAT('R42',LPAD('7',23,'0')),CONCAT('R42',LPAD('10',23,'0')),
            '$argon2id$v=19$m=65536,t=3,p=1$TEST$TEST',0,CURRENT_TIMESTAMP(6),CURRENT_TIMESTAMP(6),CURRENT_TIMESTAMP(6));
  END;
  IF got_error = FALSE THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Credential version CHECK rejection failed'; END IF;

  SET got_error = FALSE;
  BEGIN
    DECLARE CONTINUE HANDLER FOR SQLEXCEPTION SET got_error = TRUE;
    INSERT INTO atp_auth_refresh_session
      (session_id,credential_id,family_id,token_hash,credential_version,issued_at,expires_at,created_at,updated_at)
    VALUES (CONCAT('R42',LPAD('8',23,'0')),CONCAT('R42',LPAD('2',23,'0')),CONCAT('R42',LPAD('4',23,'0')),
            UNHEX(SHA2('r42-test-token',256)),1,CURRENT_TIMESTAMP(6),TIMESTAMPADD(DAY,7,CURRENT_TIMESTAMP(6)),CURRENT_TIMESTAMP(6),CURRENT_TIMESTAMP(6));
  END;
  IF got_error = FALSE THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Refresh token hash unique rejection failed'; END IF;

  SET got_error = FALSE;
  BEGIN
    DECLARE CONTINUE HANDLER FOR SQLEXCEPTION SET got_error = TRUE;
    INSERT INTO atp_auth_refresh_session
      (session_id,credential_id,family_id,token_hash,credential_version,lifecycle_status,issued_at,expires_at,created_at,updated_at)
    VALUES (CONCAT('R42',LPAD('9',23,'0')),CONCAT('R42',LPAD('2',23,'0')),CONCAT('R42',LPAD('4',23,'0')),
            UNHEX(SHA2('r42-invalid-state',256)),1,'BROKEN',CURRENT_TIMESTAMP(6),TIMESTAMPADD(DAY,7,CURRENT_TIMESTAMP(6)),CURRENT_TIMESTAMP(6),CURRENT_TIMESTAMP(6));
  END;
  IF got_error = FALSE THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Refresh session state CHECK rejection failed'; END IF;

  SET got_error = FALSE;
  BEGIN
    DECLARE CONTINUE HANDLER FOR SQLEXCEPTION SET got_error = TRUE;
    INSERT INTO atp_auth_refresh_session
      (session_id,credential_id,family_id,token_hash,credential_version,lifecycle_status,issued_at,expires_at,created_at,updated_at)
    VALUES (CONCAT('R42',LPAD('11',23,'0')),CONCAT('R42',LPAD('2',23,'0')),CONCAT('R42',LPAD('4',23,'0')),
            UNHEX(SHA2('r42-revoked-without-time',256)),1,'REVOKED',CURRENT_TIMESTAMP(6),TIMESTAMPADD(DAY,7,CURRENT_TIMESTAMP(6)),CURRENT_TIMESTAMP(6),CURRENT_TIMESTAMP(6));
  END;
  IF got_error = FALSE THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Refresh revoked-state coherence rejection failed'; END IF;
END//
CALL assert_r4_contract()//
DROP PROCEDURE assert_r4_contract//
DELIMITER ;

SET @audit_update_trigger_count := (
  SELECT COUNT(*) FROM information_schema.triggers
  WHERE trigger_schema = DATABASE() AND trigger_name = 'trg_atp_auth_security_audit_no_update'
);
SET @audit_delete_trigger_count := (
  SELECT COUNT(*) FROM information_schema.triggers
  WHERE trigger_schema = DATABASE() AND trigger_name = 'trg_atp_auth_security_audit_no_delete'
);

DROP PROCEDURE IF EXISTS assert_auth_audit_triggers;
DELIMITER $$
CREATE PROCEDURE assert_auth_audit_triggers()
BEGIN
  IF @audit_update_trigger_count <> 1 OR @audit_delete_trigger_count <> 1 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Expected append-only auth audit triggers';
  END IF;
END$$
DELIMITER ;
CALL assert_auth_audit_triggers();
DROP PROCEDURE assert_auth_audit_triggers;

SELECT 'CURRENT_AUTHORITY_MYSQL84_GATE_PASS' AS result;
