# LIBRARIES - SQLITE DATABASE 
import pandas as pd
import sqlite3

# DATABASE CONNECT
database = 'ssc_database.db'
connection_db = sqlite3.connect(database)
cursor = connection_db.cursor()
connection_db.execute("PRAGMA foreign_keys = ON")

# DATABASE SCHEMA
# Locations
cursor.execute("DROP TABLE IF EXISTS locations;")
cursor.execute("""CREATE TABLE locations (
                location_id VARCHAR(10) NOT NULL PRIMARY KEY,
                location_name VARCHAR(255) NOT NULL,
                street_number VARCHAR(255) NOT NULL,
                postal_code VARCHAR(8),
                city VARCHAR(150),
                country VARCHAR(150)
                );""" ) 
# Event Types
cursor.execute("DROP TABLE IF EXISTS event_types;")
cursor.execute("""CREATE TABLE event_types (
                etype_id VARCHAR(5) NOT NULL PRIMARY KEY,
                etype_name VARCHAR(255) NOT NULL UNIQUE
                );""")
# Partners
cursor.execute("DROP TABLE IF EXISTS partners;")
cursor.execute("""CREATE TABLE partners (
                partner_id VARCHAR(10) NOT NULL PRIMARY KEY,
                partner_name VARCHAR(255) NOT NULL,
                partner_type VARCHAR(150),
                street_number VARCHAR(255),
                postal_code VARCHAR(8),
                city VARCHAR(150),
                country VARCHAR(150),
                contact_person VARCHAR(255) NOT NULL,
                phone_number VARCHAR(12) NOt NULL,
                email_address VARCHAR(255) NOT NULL,
                website VARCHAR(255),
                status VARCHAR(30) DEFAULT 'Active'
                    CHECK (status IN ('Active', 'Inactive')),
                partner_since INTEGER
                );""")

# Events
cursor.execute("DROP TABLE IF EXISTS events;")
cursor.execute("""CREATE TABLE events (
                event_id INTEGER NOT NULL PRIMARY KEY,
                location_id VARCHAR(20) NOT NULL,
                event_type VARCHAR(5) NOT NULL,
                partner_id VARCHAR(6) NOT NULL,
                event_name VARCHAR(255) NOT NULL,
                start_datetime DATETIME NOT NULL,
                end_datetime DATETIME NOT NULL,
                age_rating VARCHAR(20),
                ticket_cost DECIMAL(10,2)
                    CHECK (ticket_cost >= 0),
                accessibility TEXT,

                CONSTRAINT events_fk1 FOREIGN KEY(location_id) REFERENCES locations(location_id),
                CONSTRAINT events_fk2 FOREIGN KEY(event_type) REFERENCES event_types(etype_id),
                CONSTRAINT events_fk3 FOREIGN KEY(partner_id) REFERENCES partners(partner_id)
                );""")

# Participants
cursor.execute("DROP TABLE IF EXISTS participants;")
cursor.execute("""CREATE TABLE participants (
                participant_id VARCHAR(10) NOT NULL PRIMARY KEY,
                participant_name VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE,
                phone_number VARCHAR(10) UNIQUE,
                address VARCHAR(100),
                city VARCHAR(150),
                country VARCHAR(150),
                dob DATE,
                whatsapp_groupchat BOOLEAN,
                have_connect BOOLEAN,
                marketing_subs BOOLEAN
                );""")

# Event Registration
cursor.execute("DROP TABLE IF EXISTS event_registration;")
cursor.execute("""CREATE TABLE event_registration (
                registration_id VARCHAR(10) NOT NULL PRIMARY KEY,
                registered_by VARCHAR(10) NOT NULL,
                event_id INTEGER NOT NULL,
                datetime_registered DATETIME,
                number_of_attendee INTEGER NOT NULL
                    CHECK (number_of_attendee >=1),
                channel VARCHAR(20) 
                    CHECK (channel IN ('Connect', 'Whatsapp', 'Walk-in')),
                status VARCHAR(30) DEFAULT 'Registered'
                    CHECK (status IN ('Registered', 'Cancelled', 'Waitlisted')),
                notes TEXT,

                CONSTRAINT event_registration_fk1 FOREIGN KEY(registered_by) REFERENCES participants(participant_id),
                CONSTRAINT event_registration_fk2 FOREIGN KEY(event_id) REFERENCES events(event_id)
                );""")

# Event Registered Attendee
cursor.execute("DROP TABLE IF EXISTS event_registered_attendee;")
cursor.execute("""CREATE TABLE event_registered_attendee (
                registration_id VARCHAR(10) NOT NULL,
                participant_id VARCHAR(10) NOT NULL,
                role VARCHAR(20) NOT NULL
                    CHECK (role IN ('Main Attendee', 'Guest')),
                need_buddy BOOLEAN,
                attendance_status VARCHAR(20) DEFAULT 'Not Checked In'
                    CHECK (attendance_status IN ('Not Checked In', 'Attended', 'No Show', 'Cancelled')),
                checkin_datetime DATETIME,
                
                CONSTRAINT event_registered_attendee_pk PRIMARY KEY(registration_id, participant_id),
                CONSTRAINT event_regsitered_attendee_fk1 FOREIGN KEY(registration_id) REFERENCES event_registration(registration_id),
                CONSTRAINT event_registered_attendee_fk2 FOREIGN KEY(participant_id) REFERENCES participants(participant_id)
                );""")

# SAVE & DISCONNECT
connection_db.commit()
connection_db.close()