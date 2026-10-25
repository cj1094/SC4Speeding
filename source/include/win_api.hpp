#pragma once
#include <stdint.h>
typedef void* HANDLE;
typedef unsigned long DWORD;
typedef int BOOL;
extern "C" {
__declspec(dllimport) void* __stdcall GetModuleHandleA(const char*);
__declspec(dllimport) DWORD __stdcall GetModuleFileNameA(void*,char*,DWORD);
__declspec(dllimport) DWORD __stdcall GetTickCount();
__declspec(dllimport) DWORD __stdcall GetCurrentThreadId();
__declspec(dllimport) short __stdcall GetAsyncKeyState(int);
__declspec(dllimport) BOOL __stdcall DisableThreadLibraryCalls(void*);
__declspec(dllimport) HANDLE __stdcall CreateFileA(const char*,DWORD,DWORD,void*,DWORD,DWORD,HANDLE);
__declspec(dllimport) BOOL __stdcall WriteFile(HANDLE,const void*,DWORD,DWORD*,void*);
__declspec(dllimport) BOOL __stdcall CloseHandle(HANDLE);
__declspec(dllimport) unsigned int __stdcall GetPrivateProfileIntA(const char*,const char*,int,const char*);
}
