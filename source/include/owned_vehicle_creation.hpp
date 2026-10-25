// Alternate entry for this plugin's calls only. No EXE/vtable writes.
// Retains native activation/priority checks, skips the population-cap/reclaim gate.
static __declspec(naked) void owned_vehicle_core(){
    __asm {
        sub esp,18h
        push ebx
        mov bl,byte ptr [esp+30h]
        cmp bl,0ffh
        push ebp
        push esi
        push edi
        mov esi,ecx
        mov dword ptr [esp+10h],0
        mov byte ptr [esp+3ch],bl
        jae ordinary_gate
        mov ecx,dword ptr ds:[0b43cech]
        test ecx,ecx
        je ordinary_gate
        mov eax,[ecx]
        call dword ptr [eax+0c4h]
        mov edi,eax
        test edi,edi
        je ordinary_gate
        mov eax,[esp+2ch]
        mov edx,[edi]
        push eax
        mov ecx,edi
        call dword ptr [edx+4ch]
        test al,al
        je ordinary_gate
        mov edx,[edi]
        mov ecx,edi
        call dword ptr [edx+6ch]
        movzx ebp,al
        mov eax,[edi]
        mov ecx,edi
        call dword ptr [eax+70h]
        cmp eax,ebp
        jae ordinary_gate
        mov bl,0feh
        mov byte ptr [esp+3ch],bl
        jmp capacity_gate
    ordinary_gate:
        test bl,bl
        jne capacity_gate
        mov al,[esi+4ch]
        test al,al
        jne capacity_gate
        jmp rejected
    capacity_gate:
        // This private call has at most two scene cars. Do not inspect or
        // alter shared maxima, and do not reclaim unrelated traffic.
        mov eax,0510732h
        jmp eax
    rejected:
        mov eax,0510726h
        jmp eax
    }
}
static __declspec(naked) cISC4Automaton* __fastcall owned_vehicle_outer(
    cISC4AutomataManager*,void*,uint32_t,const cS3DVector3&,uint32_t,
    const cGZPersistResourceKey&,cIGZMessageTarget2*,uint8_t,const cS3DVector3*){
    __asm {
        mov edx,[esp+10h]
        push esi
        push edi
        mov edi,ecx
        mov ecx,[esp+20h]
        push ecx
        mov ecx,[esp+18h]
        push 0
        push edx
        mov edx,[esp+18h]
        push ecx
        push edx
        mov ecx,edi
        call owned_vehicle_core
        mov edx,0505394h
        jmp edx
    }
}
static uint32_t native_code_hash(uintptr_t address,unsigned size){
    uint32_t hash=2166136261u;auto bytes=reinterpret_cast<const uint8_t*>(address);
    for(unsigned i=0;i<size;++i)hash=(hash^bytes[i])*16777619u;return hash;
}
static bool owned_vehicle_creation_supported(cISC4AutomataManager* manager){
    auto table=*reinterpret_cast<uintptr_t**>(manager);
    return table[15]==0x505370 && table[46]==0x510690 &&
        native_code_hash(0x505370,0x6b)==0x6599ba45 && native_code_hash(0x510690,0x249)==0x14328c33;
}
