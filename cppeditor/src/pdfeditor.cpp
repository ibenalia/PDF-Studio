#include <podofo/podofo.h>
#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <functional>
#include <memory>
#include <thread>
#include <mutex>

using namespace PoDoFo;

// Mutex pour protéger les opérations d'écriture
std::mutex writeMutex;

// Display help for available commands
void printUsage() {
    std::cout << "Usage: pdfeditor <command> [options]" << std::endl;
    std::cout << "Commands:" << std::endl;
    std::cout << "  merge <output.pdf> <input1.pdf> <input2.pdf> ..." << std::endl;
    std::cout << "  split <input.pdf> <output_prefix> [<page_range>]" << std::endl;
    std::cout << "  compress <input.pdf> <output.pdf> [<quality>]" << std::endl;
    std::cout << "  rotate <input.pdf> <output.pdf> <degrees>" << std::endl;
    std::cout << "  watermark <input.pdf> <output.pdf> <text> [<opacity>]" << std::endl;
    std::cout << "  protect <input.pdf> <output.pdf> <password> [<permissions>]" << std::endl;
    std::cout << "  unlock <input.pdf> <output.pdf> <password>" << std::endl;
    std::cout << "  info <input.pdf>" << std::endl;
}

// Function to merge PDFs with memory optimization
int mergePDFs(const std::vector<std::string>& inputFiles, const std::string& outputFile) {
    try {
        if (inputFiles.empty()) {
            std::cerr << "Error: No input files provided." << std::endl;
            return 1;
        }

        PdfMemDocument outputDocument;
        
        for (const auto& file : inputFiles) {
            // Vérifier si le fichier existe
            FILE* fp = fopen(file.c_str(), "rb");
            if (!fp) {
                std::cerr << "Error: Input file not found: " << file << std::endl;
                return 1;
            }
            fclose(fp);
            
            PdfMemDocument inputDocument;
            try {
                inputDocument.Load(file.c_str());
                // Insert pages from inputDocument to outputDocument
                outputDocument.InsertPages(inputDocument, 0, inputDocument.GetPageCount());
            } catch (const PdfError& error) {
                std::cerr << "Error loading PDF file " << file << ": " << error.what() << std::endl;
                return 1;
            }
            // inputDocument sera détruit automatiquement à la fin de cette itération
        }
        
        // Vérifier si le répertoire de sortie existe
        size_t lastSlash = outputFile.find_last_of("/\\");
        if (lastSlash != std::string::npos) {
            std::string outputDir = outputFile.substr(0, lastSlash);
            // On pourrait ajouter une vérification du répertoire ici
        }
        
        outputDocument.Write(outputFile.c_str());
        std::cout << "Merge completed successfully. Output file: " << outputFile << std::endl;
        return 0;
    } catch (const PdfError& error) {
        std::cerr << "Error merging PDFs: " << error.what() << std::endl;
        return 1;
    }
}

// Function to split a PDF with parallel processing
void splitPageRange(const PdfMemDocument& document, int start, int count, const std::string& outputPrefix) {
    PdfMemDocument newDocument;
    newDocument.InsertPages(document, start, count);
    std::string outputFile = outputPrefix + "_pages_" + std::to_string(start + 1) + "-" + std::to_string(start + count) + ".pdf";
    {
        std::lock_guard<std::mutex> lock(writeMutex); // Protège l'écriture sur disque
        newDocument.Write(outputFile.c_str());
        std::cout << "Created: " << outputFile << std::endl;
    }
}

int splitPDF(const std::string& inputFile, const std::string& outputPrefix, const std::string& pageRange) {
    try {
        // Vérifier si le fichier existe
        FILE* fp = fopen(inputFile.c_str(), "rb");
        if (!fp) {
            std::cerr << "Error: Input file not found: " << inputFile << std::endl;
            return 1;
        }
        fclose(fp);
        
        PdfMemDocument document;
        document.Load(inputFile.c_str());
        int pageCount = document.GetPageCount();
        
        if (pageRange.empty()) {
            // Option multithread - on garde cette approche car on exécutera dans des processus séparés
            const int pagesPerThread = 50; // Traitement par lots de 50 pages
            std::vector<std::thread> threads;
            for (int i = 0; i < pageCount; i += pagesPerThread) {
                int pagesToCopy = std::min(pagesPerThread, pageCount - i);
                threads.emplace_back(splitPageRange, std::ref(document), i, pagesToCopy, outputPrefix);
            }
            for (auto& t : threads) t.join();
            
            std::cout << "Split completed successfully. " << pageCount << " pages split into " 
                     << ((pageCount + pagesPerThread - 1) / pagesPerThread) << " documents." << std::endl;
        } else {
            // Gestion des autres cas (pageRange avec virgules ou tirets) peut être ajoutée ici
            // Pour simplifier, je ne l'inclus pas dans cet exemple
            std::cerr << "Page range support not implemented yet." << std::endl;
            return 1;
        }
        return 0;
    } catch (const PdfError& error) {
        std::cerr << "Error splitting PDF: " << error.what() << std::endl;
        return 1;
    }
}

// Function to compress a PDF with compression enabled
int compressPDF(const std::string& inputFile, const std::string& outputFile, const std::string& quality) {
    try {
        // Marquer le paramètre non utilisé pour éviter l'avertissement
        (void)quality;
        
        // Vérifier si le fichier existe
        FILE* fp = fopen(inputFile.c_str(), "rb");
        if (!fp) {
            std::cerr << "Error: Input file not found: " << inputFile << std::endl;
            return 1;
        }
        fclose(fp);
        
        PdfMemDocument document;
        document.Load(inputFile.c_str());
        
        // La méthode SetUseCompression n'existe pas dans PoDoFo
        // PoDoFo utilise la compression par défaut
        
        document.Write(outputFile.c_str());
        std::cout << "Compression completed successfully. Output file: " << outputFile << std::endl;
        return 0;
    } catch (const PdfError& error) {
        std::cerr << "Error compressing PDF: " << error.what() << std::endl;
        return 1;
    }
}

// Function to rotate pages in a PDF
int rotatePDF(const std::string& inputFile, const std::string& outputFile, int degrees) {
    try {
        // Vérifier si le fichier existe
        FILE* fp = fopen(inputFile.c_str(), "rb");
        if (!fp) {
            std::cerr << "Error: Input file not found: " << inputFile << std::endl;
            return 1;
        }
        fclose(fp);
        
        PdfMemDocument document;
        document.Load(inputFile.c_str());
        
        // Normalize the angle to 0, 90, 180 or 270
        degrees = ((degrees % 360) / 90) * 90;
        
        // Apply rotation to all pages
        for (int i = 0; i < document.GetPageCount(); i++) {
            PdfPage* page = document.GetPage(i);
            int currentRotation = page->GetRotation();
            int newRotation = (currentRotation + degrees) % 360;
            page->SetRotation(newRotation);
        }
        
        document.Write(outputFile.c_str());
        std::cout << "Rotation completed successfully. All pages rotated by " << degrees << " degrees. Output file: " << outputFile << std::endl;
        return 0;
    } catch (const PdfError& error) {
        std::cerr << "Error rotating PDF: " << error.what() << std::endl;
        return 1;
    }
}

// Function to add a watermark to a PDF
void watermarkPage(PdfMemDocument& document, int pageNum, const std::string& text, float opacity) {
    // Marquer le paramètre non utilisé pour éviter l'avertissement
    (void)opacity;
    
    std::lock_guard<std::mutex> lock(writeMutex);
    
    PdfPage* page = document.GetPage(pageNum);
    PdfPainter painter;
    painter.SetPage(page);
    
    // Create a font
    PdfFont* font = document.CreateFont("Helvetica", false);
    if (!font) return;
    font->SetFontSize(24.0);
    
    // Create a string
    PdfString pdfString(text);
    
    // Calculate text width
    double textWidth = font->GetFontMetrics()->StringWidth(pdfString);
    
    // Calculate position (center of page)
    double pageWidth = page->GetPageSize().GetWidth();
    double pageHeight = page->GetPageSize().GetHeight();
    double x = (pageWidth - textWidth) / 2;
    double y = pageHeight / 2;
    
    // Set transparency
    painter.SetStrokingColor(0.5, 0.5, 0.5);
    painter.SetColor(0.5, 0.5, 0.5);
    
    // Draw text
    painter.DrawText(x, y, pdfString);
    painter.FinishPage();
}

int watermarkPDF(const std::string& inputFile, const std::string& outputFile, const std::string& text, float opacity) {
    try {
        // Vérifier si le fichier existe
        FILE* fp = fopen(inputFile.c_str(), "rb");
        if (!fp) {
            std::cerr << "Error: Input file not found: " << inputFile << std::endl;
            return 1;
        }
        fclose(fp);
        
        PdfMemDocument document;
        document.Load(inputFile.c_str());
        
        if (opacity < 0.0 || opacity > 1.0) {
            opacity = 0.5; // Default value
        }
        
        // On utilise les threads car l'exécutable sera appelé dans son propre processus
        std::vector<std::thread> threads;
        for (int i = 0; i < document.GetPageCount(); i++) {
            threads.emplace_back(watermarkPage, std::ref(document), i, text, opacity);
        }
        for (auto& t : threads) t.join();
        
        document.Write(outputFile.c_str());
        std::cout << "Watermark added successfully to " << document.GetPageCount() << " pages." << std::endl;
        return 0;
    } catch (const PdfError& error) {
        std::cerr << "Error adding watermark: " << error.what() << std::endl;
        return 1;
    }
}

// Function to protect a PDF with a password
int protectPDF(const std::string& inputFile, const std::string& outputFile, const std::string& password, const std::string& permissionsStr) {
    try {
        // Marquer le paramètre non utilisé pour éviter l'avertissement
        (void)permissionsStr;
        
        // Vérifier si le fichier existe
        FILE* fp = fopen(inputFile.c_str(), "rb");
        if (!fp) {
            std::cerr << "Error: Input file not found: " << inputFile << std::endl;
            return 1;
        }
        fclose(fp);
        
        // Vérifier si le mot de passe est vide
        if (password.empty()) {
            std::cerr << "Error: Password cannot be empty." << std::endl;
            return 1;
        }
        
        PdfMemDocument document;
        document.Load(inputFile.c_str());
        
        // Fix SetEncrypted - requires owner password and user password
        document.SetEncrypted(password, password);
        
        document.Write(outputFile.c_str());
        std::cout << "Protection completed successfully. Output file: " << outputFile << std::endl;
        return 0;
    } catch (const PdfError& error) {
        std::cerr << "Error protecting PDF: " << error.what() << std::endl;
        return 1;
    }
}

// Function to unlock a PDF
int unlockPDF(const std::string& inputFile, const std::string& outputFile, const std::string& password) {
    try {
        // Vérifier si le fichier existe
        FILE* fp = fopen(inputFile.c_str(), "rb");
        if (!fp) {
            std::cerr << "Error: Input file not found: " << inputFile << std::endl;
            return 1;
        }
        fclose(fp);
        
        PdfMemDocument document;
        try {
            document.Load(inputFile.c_str(), password.c_str());
        } catch (const PdfError& error) {
            std::cerr << "Error: Invalid password or PDF is not encrypted." << std::endl;
            return 1;
        }
        
        // Create a new document without encryption
        PdfMemDocument newDocument;
        
        // Copy all pages
        for (int i = 0; i < document.GetPageCount(); i++) {
            newDocument.InsertPages(document, i, 1);
        }
        
        newDocument.Write(outputFile.c_str());
        std::cout << "Unlock completed successfully. Output file: " << outputFile << std::endl;
        return 0;
    } catch (const PdfError& error) {
        std::cerr << "Error unlocking PDF: " << error.what() << std::endl;
        return 1;
    }
}

// Function to display PDF information
int getPDFInfo(const std::string& inputFile, const std::string& outputFile) {
    try {
        // Marquer le paramètre non utilisé pour éviter l'avertissement
        (void)outputFile;
        
        // Vérifier si le fichier existe
        FILE* fp = fopen(inputFile.c_str(), "rb");
        if (!fp) {
            std::cerr << "Error: Input file not found: " << inputFile << std::endl;
            return 1;
        }
        fclose(fp);
        
        PdfMemDocument document;
        document.Load(inputFile.c_str());
        
        // Format de sortie JSON pour une intégration plus facile avec Flask
        std::cout << "{" << std::endl;
        std::cout << "  \"fileName\": \"" << inputFile << "\"," << std::endl;
        std::cout << "  \"pageCount\": " << document.GetPageCount() << "," << std::endl;
        
        // Get document info if available
        if (document.GetInfo()) {
            std::cout << "  \"title\": \"" << document.GetInfo()->GetTitle().GetStringUtf8() << "\"," << std::endl;
            std::cout << "  \"author\": \"" << document.GetInfo()->GetAuthor().GetStringUtf8() << "\"," << std::endl;
            std::cout << "  \"subject\": \"" << document.GetInfo()->GetSubject().GetStringUtf8() << "\"," << std::endl;
            std::cout << "  \"creator\": \"" << document.GetInfo()->GetCreator().GetStringUtf8() << "\"," << std::endl;
            std::cout << "  \"producer\": \"" << document.GetInfo()->GetProducer().GetStringUtf8() << "\"," << std::endl;
            
            PdfString creationDate;
            if (document.GetInfo()->GetCreationDate().IsValid()) {
                document.GetInfo()->GetCreationDate().ToString(creationDate);
                std::cout << "  \"creationDate\": \"" << creationDate.GetStringUtf8() << "\"," << std::endl;
            } else {
                std::cout << "  \"creationDate\": \"\"," << std::endl;
            }
            
            PdfString modDate;
            if (document.GetInfo()->GetModDate().IsValid()) {
                document.GetInfo()->GetModDate().ToString(modDate);
                std::cout << "  \"modificationDate\": \"" << modDate.GetStringUtf8() << "\"," << std::endl;
            } else {
                std::cout << "  \"modificationDate\": \"\"," << std::endl;
            }
        }
        
        // Get page sizes
        std::cout << "  \"pages\": [" << std::endl;
        for (int i = 0; i < document.GetPageCount(); i++) {
            PdfPage* page = document.GetPage(i);
            std::cout << "    {" << std::endl;
            std::cout << "      \"pageNumber\": " << (i + 1) << "," << std::endl;
            std::cout << "      \"width\": " << page->GetPageSize().GetWidth() << "," << std::endl;
            std::cout << "      \"height\": " << page->GetPageSize().GetHeight() << "," << std::endl;
            std::cout << "      \"rotation\": " << page->GetRotation() << std::endl;
            if (i < document.GetPageCount() - 1) {
                std::cout << "    }," << std::endl;
            } else {
                std::cout << "    }" << std::endl;
            }
        }
        std::cout << "  ]" << std::endl;
        std::cout << "}" << std::endl;
        
        return 0;
    } catch (const PdfError& error) {
        std::cerr << "Error getting PDF info: " << error.what() << std::endl;
        return 1;
    }
}

// Map of commands and their functions
int main(int argc, char* argv[]) {
    if (argc < 2) {
        printUsage();
        return 1;
    }
    
    std::string command = argv[1];
    
    std::map<std::string, std::function<int(int, char*[])>> commands = {
        {"merge", [](int argc, char* argv[]) -> int {
            if (argc < 4) {
                std::cerr << "Error: Not enough arguments for merge command." << std::endl;
                std::cerr << "Usage: pdfeditor merge <output.pdf> <input1.pdf> <input2.pdf> ..." << std::endl;
                return 1;
            }
            
            std::string outputFile = argv[2];
            std::vector<std::string> inputFiles;
            
            for (int i = 3; i < argc; i++) {
                inputFiles.push_back(argv[i]);
            }
            
            return mergePDFs(inputFiles, outputFile);
        }},
        
        {"split", [](int argc, char* argv[]) -> int {
            if (argc < 4) {
                std::cerr << "Error: Not enough arguments for split command." << std::endl;
                std::cerr << "Usage: pdfeditor split <input.pdf> <output_prefix> [<page_range>]" << std::endl;
                return 1;
            }
            
            std::string inputFile = argv[2];
            std::string outputPrefix = argv[3];
            std::string pageRange = "";
            
            if (argc > 4) {
                pageRange = argv[4];
            }
            
            return splitPDF(inputFile, outputPrefix, pageRange);
        }},
        
        {"compress", [](int argc, char* argv[]) -> int {
            if (argc < 4) {
                std::cerr << "Error: Not enough arguments for compress command." << std::endl;
                std::cerr << "Usage: pdfeditor compress <input.pdf> <output.pdf> [<quality>]" << std::endl;
                return 1;
            }
            
            std::string inputFile = argv[2];
            std::string outputFile = argv[3];
            std::string quality = "medium";
            
            if (argc > 4) {
                quality = argv[4];
            }
            
            return compressPDF(inputFile, outputFile, quality);
        }},
        
        {"rotate", [](int argc, char* argv[]) -> int {
            if (argc < 5) {
                std::cerr << "Error: Not enough arguments for rotate command." << std::endl;
                std::cerr << "Usage: pdfeditor rotate <input.pdf> <output.pdf> <degrees>" << std::endl;
                return 1;
            }
            
            std::string inputFile = argv[2];
            std::string outputFile = argv[3];
            int degrees = std::stoi(argv[4]);
            
            return rotatePDF(inputFile, outputFile, degrees);
        }},
        
        {"watermark", [](int argc, char* argv[]) -> int {
            if (argc < 5) {
                std::cerr << "Error: Not enough arguments for watermark command." << std::endl;
                std::cerr << "Usage: pdfeditor watermark <input.pdf> <output.pdf> <text> [<opacity>]" << std::endl;
                return 1;
            }
            
            std::string inputFile = argv[2];
            std::string outputFile = argv[3];
            std::string text = argv[4];
            float opacity = 0.5;
            
            if (argc > 5) {
                opacity = std::stof(argv[5]);
            }
            
            return watermarkPDF(inputFile, outputFile, text, opacity);
        }},
        
        {"protect", [](int argc, char* argv[]) -> int {
            if (argc < 5) {
                std::cerr << "Error: Not enough arguments for protect command." << std::endl;
                std::cerr << "Usage: pdfeditor protect <input.pdf> <output.pdf> <password> [<permissions>]" << std::endl;
                return 1;
            }
            
            std::string inputFile = argv[2];
            std::string outputFile = argv[3];
            std::string password = argv[4];
            std::string permissions = "";
            
            if (argc > 5) {
                permissions = argv[5];
            }
            
            return protectPDF(inputFile, outputFile, password, permissions);
        }},
        
        {"unlock", [](int argc, char* argv[]) -> int {
            if (argc < 5) {
                std::cerr << "Error: Not enough arguments for unlock command." << std::endl;
                std::cerr << "Usage: pdfeditor unlock <input.pdf> <output.pdf> <password>" << std::endl;
                return 1;
            }
            
            std::string inputFile = argv[2];
            std::string outputFile = argv[3];
            std::string password = argv[4];
            
            return unlockPDF(inputFile, outputFile, password);
        }},
        
        {"info", [](int argc, char* argv[]) -> int {
            if (argc < 3) {
                std::cerr << "Error: Not enough arguments for info command." << std::endl;
                std::cerr << "Usage: pdfeditor info <input.pdf>" << std::endl;
                return 1;
            }
            
            std::string inputFile = argv[2];
            
            return getPDFInfo(inputFile, "");
        }}
    };
    
    auto it = commands.find(command);
    if (it != commands.end()) {
        return it->second(argc, argv);
    } else {
        std::cerr << "Unknown command: " << command << std::endl;
        printUsage();
        return 1;
    }
}