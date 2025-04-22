CREATE OR REPLACE FUNCTION horario_add()
RETURNS TRIGGER AS $$
BEGIN
    
    IF EXISTS (
        SELECT 1
        FROM horarios_disponiveis
        WHERE nif = OLD.nif AND nome = OLD.nome AND data = OLD.data AND hora = OLD.hora
    ) THEN
        
        RAISE EXCEPTION 'Schedule not available: exclusion canceled  ';
    END IF;

    
    INSERT INTO horarios_disponiveis (nif, nome, data, hora)
    VALUES (OLD.nif, OLD.nome, OLD.data, OLD.hora);

    RETURN OLD;
END;
$$ LANGUAGE plpgsql;


CREATE TRIGGER cancel_consulta_trigger
BEFORE DELETE ON consulta
FOR EACH ROW
EXECUTE FUNCTION horario_add();

CREATE OR REPLACE FUNCTION horario_remove()
RETURNS TRIGGER AS $$
BEGIN
    
    IF NOT EXISTS (
        SELECT 1
        FROM horarios_disponiveis
        WHERE nif = NEW.nif AND nome = NEW.nome AND data = NEW.data AND hora = NEW.hora
    ) THEN
        RAISE EXCEPTION 'Schedule not available: incertion canceled  ';
    END IF;

    DELETE FROM horarios_disponiveis
    WHERE nif = NEW.nif AND nome = NEW.nome AND data = NEW.data AND hora = NEW.hora;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER add_consulta_trigger
BEFORE INSERT ON consulta
FOR EACH ROW
EXECUTE FUNCTION horario_remove();
