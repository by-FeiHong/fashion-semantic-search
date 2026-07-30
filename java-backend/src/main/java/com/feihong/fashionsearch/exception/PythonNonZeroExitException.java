package com.feihong.fashionsearch.exception;

public class PythonNonZeroExitException extends SearchServiceException {
    private final int exitCode;

    public PythonNonZeroExitException(String message, int exitCode) {
        super(message);
        this.exitCode = exitCode;
    }

    public int getExitCode() {
        return exitCode;
    }
}
