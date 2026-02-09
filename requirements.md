# ️ DevOps Project Assignment: Deploy a Note-Taking Web App on EC2

## Project Title
Deploy a Note-Taking Website on AWS EC2 with Backup Strategy

## Objective
Set up and deploy a basic note-taking web application on an AWS EC2 instance using either Go or Python, connect it to a MariaDB database, and implement a backup solution using an additional EBS volume.

## Prerequisites
Before starting, ensure the following:
1. ✅ AWS Free Tier Account
2. ✅ EC2 instance created using Red Hat Enterprise Linux 10 (t2.micro)
3. ✅ Basic knowledge of:
    * Go or Python
    * SQL (basic CRUD operations)

## Project Requirements
1. **Create EC2 Instance**
    * OS: RHEL 10
    * Type: t2.micro or t3.micro
    * Security Groups must allow ports: 22 (SSH), 80 (HTTP)
    * Use key pair for SSH access
2. **Develop and Deploy a Web Application**
    * Language: Go or Python
    * Feature: A simple interface for users to write and submit notes
    * Functionality: Submitted notes are stored with timestamp and displayed below the input form
3. **Configure MariaDB**
    * Install MariaDB on the EC2 instance
    * Create a database and table to store notes
    * Connect your application to the database
4. **Create and Mount Backup Volume**
    * Create a new EBS volume from AWS Console
    * Attach and mount it under `/backup` on the EC2 instance
    * Implement a process to back up the MariaDB data to this volume

## Example: User Input & Output

**User Input Form (via browser):**

```
[ Write your note here... ]

[ Save Note ]
```

**Example Note:**

```
"Don't forget to review the IAM policy lecture notes."
```

**Expected Output on Webpage:**

```
* 2025-07-12 21:15:07

* Don't forget to review the IAM policy lecture notes.
```

Each new note should appear at the top with its date and time of creation.

## Deliverables
Your students should deliver:
* ✅ Source code for the web app (Go or Python)
* ✅ Screenshots of the running app on EC2
* ✅ MariaDB schema and tables
* ✅ Configuration of mounted volume `/backup`
* ✅ Evidence of database backup stored in `/backup`
* ✅ Documentation (README.md or PDF) explaining the setup steps