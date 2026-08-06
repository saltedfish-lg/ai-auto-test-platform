-- R4 MySQL 8.4 runtime assertions
DELIMITER //
CREATE PROCEDURE assert_r4_contract()
BEGIN
  DECLARE got_error BOOLEAN DEFAULT FALSE;

  IF (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_type='BASE TABLE') <> 82 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Expected exactly 82 base tables';
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
END//
CALL assert_r4_contract()//
DROP PROCEDURE assert_r4_contract//
DELIMITER ;
SELECT 'R4_MYSQL84_GATE_PASS' AS result;
