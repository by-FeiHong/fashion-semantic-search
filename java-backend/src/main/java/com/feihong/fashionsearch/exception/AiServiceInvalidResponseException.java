package com.feihong.fashionsearch.exception;

public class AiServiceInvalidResponseException extends SearchServiceException {
    public AiServiceInvalidResponseException(String message) { super(message); }
    public AiServiceInvalidResponseException(String message, Throwable cause) { super(message, cause); }
}
