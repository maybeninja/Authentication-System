# Authentication Server API Documentation

## Overview
This API provides a robust license and application management system with secure endpoints for creating, updating, and verifying application licenses.

## Base Endpoint
- **Base URL**: `/{base}` (where `base` is set to `'Auth'`)
- **Authorization**: All endpoints require a Bearer token for authentication

## Endpoints

### 1. Server Status
- **Endpoint**: `GET /Auth`
- **Description**: Check server status
- **Success Status Code**: `200 OK`
- **Response**:
  ```json
  {
    "message": "Auth Server Running",
    "discord": "https://discord.gg/tz36haKsMh"
  }
  ```
- **Error Status Codes**:
  - `401 Unauthorized`: Invalid or missing authorization token

### 2. Create Application
- **Endpoint**: `POST /Auth/create-app`
- **Description**: Register a new application
- **Success Status Code**: `201 Created`
- **Request Body**:
  ```json
  {
    "app_name": "MyApp",
    "version": "1.0.0",
    "link": "https://myapp.com/download"
  }
  ```
- **Success Response**:
  ```json
  {
    "app_name": "MyApp",
    "app_secret": "RandomGeneratedSecret",
    "app_id": "12345678",
    "version": "1.0.0",
    "link": "https://myapp.com/download"
  }
  ```
- **Error Status Codes**:
  - `400 Bad Request`: Missing required parameters
  - `401 Unauthorized`: Invalid authorization token

### 3. Update Application Version
- **Endpoint**: `POST /Auth/update-version`
- **Description**: Update an existing application's version and download link
- **Success Status Code**: `200 OK`
- **Request Body**:
  ```json
  {
    "app_name": "MyApp",
    "version": "1.1.0",
    "link": "https://myapp.com/download/v1.1.0"
  }
  ```
- **Success Response**: `{"message": "Version And Link Updated"}`
- **Error Status Codes**:
  - `400 Bad Request`: Missing app_name or version
  - `401 Unauthorized`: Invalid authorization token
  - `404 Not Found`: App does not exist
  - `500 Internal Server Error`: Corrupted app data

### 4. Generate Licenses
- **Endpoint**: `POST /Auth/gen-license`
- **Description**: Generate multiple licenses for an application
- **Success Status Code**: `201 Created`
- **Request Body**:
  ```json
  {
    "app_name": "MyApp",
    "duration": "Month",  // Options: "Month", "Year", "Lifetime"
    "quantity": 10
  }
  ```
- **Success Response**: `{"message": "10 licenses generated successfully"}`
- **Error Status Codes**:
  - `400 Bad Request`: 
    - Missing app_name
    - Missing duration
    - Missing or invalid quantity
    - Invalid duration type
  - `401 Unauthorized`: Invalid authorization token
  - `404 Not Found`: App does not exist

### 5. Assign License
- **Endpoint**: `POST /Auth/assign-license`
- **Description**: Assign an available license for a specific duration
- **Success Status Code**: `200 OK`
- **Request Body**:
  ```json
  {
    "app_name": "MyApp",
    "duration": "Month"
  }
  ```
- **Success Response**:
  ```json
  {
    "license": "MyApp-M-ABCDEFGH",
    "expiry": "2024-04-27 23:59:59"
  }
  ```
- **Error Status Codes**:
  - `400 Bad Request`: Missing app_name or duration
  - `401 Unauthorized`: Invalid authorization token
  - `404 Not Found`: 
    - App does not exist
    - No unused licenses available
  - `426 Upgrade Required`: No licenses for specified duration

### 6. Verify License
- **Endpoint**: `GET /Auth/verify-license`
- **Description**: Validate a license for an application
- **Success Status Code**: `200 OK`
- **Query Parameters**:
  - `license_key`: Generated license key
  - `app_name`: Application name
  - `app_secret`: Application secret
  - `hwid`: Hardware ID
  - `version`: Current application version
- **Success Response**:
  ```json
  {
    "message": "License valid",
    "expiry": "2024-04-27 23:59:59",
    "hwid": "unique-hardware-identifier"
  }
  ```
- **Error Status Codes**:
  - `400 Bad Request`: Missing required parameters
  - `401 Unauthorized`: Invalid app secret
  - `403 Forbidden`: 
    - License expired
    - HWID locked
  - `404 Not Found`: 
    - App not found
    - No active licenses
  - `426 Upgrade Required`: Outdated application version

### 7. Ban License
- **Endpoint**: `POST /Auth/ban-license`
- **Description**: Permanently invalidate a license
- **Success Status Code**: `200 OK`
- **Request Body**:
  ```json
  {
    "license_key": "MyApp-M-ABCDEFGH",
  }
  ```
- **Success Response**: `{"message": "License banned successfully"}`
- **Error Status Codes**:
  - `400 Bad Request`: Missing license key or app name
  - `401 Unauthorized`: Invalid authorization token
  - `404 Not Found`: 
    - App not found
    - License not found
  - `500 Internal Server Error`: Corrupted license data

### 8. Reset Hardware ID
- **Endpoint**: `POST /Auth/reset-hwid`
- **Description**: Reset the hardware ID for a specific license
- **Success Status Code**: `200 OK`
- **Request Body**:
  ```json
  {
    "license_key": "MyApp-M-ABCDEFGH",
    "user": "userid"
  }
  ```
- **Success Response**: `{"message": "HWID reset successfully"}`
- **Error Status Codes**:
  - `400 Bad Request`: Missing required parameters
  - `401 Unauthorized`: 
    - Invalid token
    - License sharing detected
  - `404 Not Found`: 
    - App not found
    - License not found
  - `500 Internal Server Error`: Corrupted license data

### 9. Update User
- **Endpoint**: `PATCH /Auth/update-user`
- **Description**: Update the user associated with a license
- **Success Status Code**: `200 OK`
- **Request Body**:
  ```json
  {
    "user": "userid",
    "license_key": "MyApp-M-ABCDEFGH"
  }
  ```
- **Success Response**: `{"message": "User updated successfully"}`
- **Error Status Codes**:
  - `400 Bad Request`: 
    - Missing app_name, user, or license_key
    - Invalid license key
  - `401 Unauthorized`: Invalid authorization token
  - `404 Not Found`: App not found
  - `500 Internal Server Error`: Corrupted license data

### 10. Get License Details
- **Endpoint**: `GET /Auth/get-license`
- **Description**: Retrieve details of a specific license
- **Success Status Code**: `200 OK`
- **Request Body**:
  ```json
  {
    "license_key": "MyApp-M-ABCDEFGH",
  }
  ```
- **Success Response**:
  ```json
  {
    "license_key": "MyApp-M-ABCDEFGH",
    "user": "username",
    "expiry_date": "2024-04-27 23:59:59",
    "valid": "Yes"
  }
  ```
- **Error Status Codes**:
  - `400 Bad Request`: Missing required parameters
  - `401 Unauthorized`: Invalid authorization token
  - `403 Forbidden`: License expired
  - `404 Not Found`: 
    - Application not found
    - License not found
  - `500 Internal Server Error`: 
    - Corrupted license data
    - Invalid expiry date format

### 11. System Health Check
- **Endpoint**: `GET /Auth/check`
- **Description**: Get system-wide license statistics
- **Success Status Code**: `200 OK`
- **Success Response**:
  ```json
  {
    "total_apps": 5,
    "total_licenses": 100
  }
  ```
- **Error Status Codes**:
  - `401 Unauthorized`: Invalid authorization token
  - `500 Internal Server Error`: Failed to retrieve system data

## Authorization
- All endpoints require a Bearer token in the Authorization header
- Unauthorized requests return a 401 status with detailed logging

## Error Handling
- Comprehensive error responses with appropriate HTTP status codes
- Detailed logging for unauthorized access attempts
- Input validation with specific error messages

## Logging
- All critical operations are logged with:
  - Timestamp
  - Operation type
  - Relevant details (IP address, app name, etc.)
  - Color-coded log levels

## Security Features
- Token-based authentication
- Hardware ID (HWID) locking
- License duration tracking
- Version compatibility checks
- User-based license management
- License banning mechanism

## Deployment Details
- Host: `0.0.0.0`
- Port: `1337`
